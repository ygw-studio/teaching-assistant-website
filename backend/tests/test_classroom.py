import importlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient


class ClassroomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.env = {key:os.environ.get(key) for key in ('DATABASE_PATH','APP_ENV','ENABLE_LOCAL_DEMO_ACCESS','AI_KEY_ENCRYPTION_KEY')}
        os.environ.update(DATABASE_PATH=str(Path(cls.temp.name)/'classroom.db'),APP_ENV='development',ENABLE_LOCAL_DEMO_ACCESS='true',AI_KEY_ENCRYPTION_KEY=Fernet.generate_key().decode())
        cls.main = importlib.import_module('app.main')
        cls.main.init_database()
        cls.main.classroom.init_classroom()
        cls.client = TestClient(cls.main.app,base_url='http://127.0.0.1:8001',client=('127.0.0.1',1234))
        cls.headers = {}
        for role in ('student','teacher','admin'):
            token = cls.client.post('/api/v1/auth/demo-session',json={'role':role}).json()['access_token']
            cls.headers[role] = {'Authorization':f'Bearer {token}'}
        for account,role,phone in [('outside-teacher','teacher','13910000001'),('second-student','student','13910000002')]:
            response = cls.client.post('/api/v1/auth/users',headers=cls.headers['admin'],json={
                'account_id':account,'password':'TestPassword123!','role':role,'name':account,'phone':phone})
            assert response.status_code == 201,response.text
            token = cls.client.post('/api/v1/auth/login',json={'account_id':account,'password':'TestPassword123!'}).json()['access_token']
            cls.headers[account] = {'Authorization':f'Bearer {token}'}
        access = cls.client.get('/api/v1/classroom/access/data-structures-python',headers=cls.headers['admin']).json()
        access['students'].append('second-student')
        cls.client.put('/api/v1/classroom/access/data-structures-python',headers=cls.headers['admin'],json=access)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        for key,value in cls.env.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value
        cls.temp.cleanup()

    def setUp(self):
        self.main.RATE_LIMIT_BUCKETS.clear()
        self.payload = {'course_id':'data-structures-python','title':'验收习题','instructions':'实现一个栈','initial_code':'x = 1','is_published':True,
                        'deadline_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
        response = self.client.post('/api/v1/classroom/assignments',headers=self.headers['teacher'],json=self.payload)
        self.assertEqual(response.status_code,201,response.text)
        self.task = response.json()
        self.attempt = self.client.post(f"/api/v1/classroom/assignments/{self.task['id']}/start",headers=self.headers['student']).json()

    def event(self,**patches):
        value = {'event_id':str(uuid4()),'session_id':'tab-1','event_type':'activity.interval','occurred_at':datetime.now(timezone.utc).isoformat(),
                 'attempt_id':self.attempt['id'],'metadata':{'visible_ms':10000,'ai_visible_ms':3000}}
        value.update(patches); return value

    def bind(self,role='student',key='sk-test-student-secret-12345'):
        return self.client.put('/api/v1/ai/key',headers=self.headers[role],json={'api_key':key,'model':'qwen-plus','free_only_confirmed':True})

    def provider(self,status=200):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.post.return_value = httpx.Response(status,json={'choices':[{'message':{'content':'可以用列表实现栈。'}}],'usage':{'total_tokens':12}})
        return client

    def test_task_resume_version_pin_and_teacher_scope(self):
        repeated = self.client.post(f"/api/v1/classroom/assignments/{self.task['id']}/start",headers=self.headers['student']).json()
        self.assertEqual(repeated['id'],self.attempt['id'])
        updated = self.client.put(f"/api/v1/classroom/assignments/{self.task['id']}",headers=self.headers['teacher'],json={**self.payload,'instructions':'新题目内容'})
        self.assertEqual(updated.status_code,200)
        repeated = self.client.post(f"/api/v1/classroom/assignments/{self.task['id']}/start",headers=self.headers['student']).json()
        self.assertEqual(repeated['task']['instructions'],'实现一个栈')
        self.assertEqual(self.client.get('/api/v1/classroom/records',headers=self.headers['outside-teacher']).json(),[])
        self.assertEqual(self.client.get(f"/api/v1/classroom/records/{self.attempt['id']}",headers=self.headers['outside-teacher']).status_code,403)
        self.assertEqual(self.client.get(f"/api/v1/classroom/attempts/{self.attempt['id']}/chat",headers=self.headers['second-student']).status_code,403)

    def test_deadline_extension_submission_idempotency_and_withdrawal(self):
        path = f"/api/v1/classroom/assignments/{self.task['id']}"
        late = {**self.payload,'deadline_at':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()}
        self.client.put(path,headers=self.headers['teacher'],json=late)
        submit_path = f"/api/v1/classroom/attempts/{self.attempt['id']}/submit"
        submission = {'request_id':str(uuid4()),'code':'print(1)','stdin':''}
        self.assertEqual(self.client.post(submit_path,headers=self.headers['student'],json=submission).status_code,409)
        self.client.put(path,headers=self.headers['teacher'],json=self.payload)
        first = self.client.post(submit_path,headers=self.headers['student'],json=submission)
        self.assertEqual(first.status_code,200,first.text)
        second = self.client.post(submit_path,headers=self.headers['student'],json=submission)
        self.assertEqual(first.json()['id'],second.json()['id'])
        detail = self.client.get(f"/api/v1/classroom/records/{self.attempt['id']}",headers=self.headers['teacher']).json()
        self.assertEqual(len(detail['submissions']),1)
        self.client.put(path,headers=self.headers['teacher'],json={**self.payload,'is_published':False})
        self.assertEqual(self.client.post(submit_path,headers=self.headers['student'],json={**submission,'request_id':str(uuid4())}).status_code,409)
        restored = self.client.post(path+'/start',headers=self.headers['student'])
        self.assertEqual(restored.status_code,200)
        self.assertEqual(restored.json()['id'],self.attempt['id'])

    def test_events_deduplicate_union_time_and_do_not_overwrite_raw(self):
        event = self.event()
        other = {**event,'event_id':str(uuid4()),'session_id':'tab-2','metadata':{'visible_ms':15000,'ai_visible_ms':4000}}
        result = self.client.post('/api/v1/classroom/events',headers=self.headers['student'],json={'events':[event,other]})
        self.assertEqual(result.json()['accepted'],2,result.text)
        repeat = self.client.post('/api/v1/classroom/events',headers=self.headers['student'],json={'events':[event,other]})
        self.assertEqual(repeat.json()['duplicates'],2)
        self.assertEqual(self.client.get('/api/v1/classroom/me/time',headers=self.headers['student']).json()['learning_ms'] % 1000000 >= 15000,True)
        from app.database import get_connection
        with get_connection() as db:
            rows = db.execute('SELECT * FROM learning_events WHERE event_id IN (?,?)',(event['event_id'],other['event_id'])).fetchall()
        self.assertEqual(self.main.classroom.activity_totals(rows),{'learning_ms':15000,'ai_panel_ms':4000})
        before = dict(rows[0])
        cleaned = self.client.post('/api/v1/classroom/events/clean',headers=self.headers['admin'])
        self.assertTrue(cleaned.json()['raw_preserved'])
        with get_connection() as db:
            after = dict(db.execute('SELECT * FROM learning_events WHERE event_id=?',(before['event_id'],)).fetchone())
        self.assertEqual(before,after)
        self.assertEqual(self.client.post('/api/v1/classroom/events/clean',headers=self.headers['teacher']).status_code,403)

    def test_rejected_batch_is_atomic_and_does_not_accept_secret_fields(self):
        good = self.event()
        bad = self.event(metadata={'api_key':'must-not-store'})
        result = self.client.post('/api/v1/classroom/events',headers=self.headers['student'],json={'events':[good,bad]})
        self.assertEqual(result.status_code,422)
        from app.database import get_connection
        with get_connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM learning_events WHERE event_id=?',(good['event_id'],)).fetchone()[0],0)
        self.assertEqual(self.client.post('/api/v1/classroom/events',headers=self.headers['student'],json={'events':[self.event(metadata={'action':{'api_key':'secret'}})]}).status_code,422)

    def test_personal_key_encrypted_not_returned_and_own_provider_used(self):
        key = 'sk-test-private-student-key-123456'
        self.assertEqual(self.bind(key=key).status_code,200)
        self.assertNotIn(key,self.client.get('/api/v1/ai/key',headers=self.headers['student']).text)
        from app.database import get_connection
        with get_connection() as db:
            encrypted = db.execute("SELECT encrypted_key FROM personal_ai_keys WHERE account_id='20250001'").fetchone()[0]
        self.assertNotIn(key,encrypted)
        provider = self.provider()
        with patch.object(self.main.qwen.httpx,'AsyncClient',return_value=provider),patch.dict(os.environ,{'AI_API_KEY':'sk-platform-must-not-run'}):
            result = self.client.post('/api/v1/ai/chat',headers=self.headers['student'],json={'account_id':'20250001','message':'什么是栈？','attempt_id':self.attempt['id']})
            self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(provider.post.call_args.kwargs['headers']['Authorization'],f'Bearer {key}')
        export = self.client.get('/api/v1/classroom/events/export',headers=self.headers['admin'])
        self.assertNotIn(key,export.text)
        detail = self.client.get(f"/api/v1/classroom/records/{self.attempt['id']}",headers=self.headers['teacher']).json()
        self.assertEqual([item['role'] for item in detail['chat']['messages']],['user','assistant'])
        self.assertEqual(len([item for item in detail['events'] if item['event_type']=='ai.replied']),1)
        self.assertEqual(self.client.get('/api/v1/ai/key',headers=self.headers['admin']).status_code,403)

    def test_quota_failure_no_fallback_and_failed_wait_recorded(self):
        self.bind()
        provider = self.provider(403)
        with patch.object(self.main.qwen.httpx,'AsyncClient',return_value=provider):
            result = self.client.post('/api/v1/ai/chat',headers=self.headers['student'],json={'account_id':'20250001','message':'直接给我答案','attempt_id':self.attempt['id']})
        self.assertEqual(result.status_code,403)
        self.assertEqual(provider.post.call_count,1)
        detail = self.client.get(f"/api/v1/classroom/records/{self.attempt['id']}",headers=self.headers['teacher']).json()
        self.assertTrue(any(item['event_type']=='ai.failed' for item in detail['events']))
        self.assertFalse(any(item['event_type']=='ai.replied' for item in detail['events']))

    def test_key_requires_free_stop_acknowledgement_and_production_secret(self):
        self.assertEqual(self.client.put('/api/v1/ai/key',headers=self.headers['student'],json={'api_key':'sk-test-valid-format'}).status_code,422)
        with patch.dict(os.environ,{'APP_ENV':'production','AI_KEY_ENCRYPTION_KEY':''}):
            self.assertEqual(self.bind().status_code,503)

    def test_workspace_key_with_dots_is_accepted_without_a_provider_call(self):
        key = 'sk-ws-test.payload_part.signature-123456'
        with patch.object(self.main.qwen.httpx, 'AsyncClient') as provider:
            result = self.bind(key=key)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertNotIn(key, result.text)
            for invalid in ('sk-test.key with space-12345', 'sk-test/key-12345', 'sk-test\nkey-12345', 'sk-' + 'a' * 501):
                self.assertEqual(self.bind(key=invalid).status_code, 422)
            provider.assert_not_called()
        saved, model = self.main.qwen.provider_key('20250001')
        self.assertEqual(saved, key)
        self.assertEqual(model, 'qwen-plus')

    def test_notebook_run_snapshot_and_real_context(self):
        result = {'outputs':[{'output_type':'stream','name':'stdout','text':'你好'}],'execution_count':1,'exit_code':0,'duration_ms':11,'kernel_reset':False}
        with patch.object(self.main.notebook_pool,'execute',return_value=result):
            response = self.client.post('/api/v1/notebooks/execute',headers=self.headers['student'],json={
                'code':"print('你好')",'notebook_source':'notebook-version','notebook_id':'kernel-1','cell_id':'cell-1',
                'resource_id':self.task['id'],'attempt_id':self.attempt['id'],'course_id':'data-structures-python'})
        self.assertEqual(response.status_code,200,response.text)
        detail = self.client.get(f"/api/v1/classroom/records/{self.attempt['id']}",headers=self.headers['teacher']).json()
        self.assertEqual(detail['snapshots'][0]['code'],'notebook-version')
        self.assertEqual([item['event_type'] for item in detail['events'] if item['event_type'].startswith('run.')],['run.started','run.finished'])


if __name__ == '__main__':
    unittest.main()
