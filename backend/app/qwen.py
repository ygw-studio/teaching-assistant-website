"""Per-account Qwen credentials; plaintext secrets never leave the provider call."""
import os
import re
import time
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, SecretStr

from .classroom import get_attempt, record_event, require_course
from .database import (get_connection, get_database_path,
                       conversation_belongs_to_account, list_messages, save_message, utc_now)

QWEN_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'


def cipher():
    configured = os.getenv('AI_KEY_ENCRYPTION_KEY','').strip()
    if configured:
        try:
            return Fernet(configured.encode('ascii'))
        except (ValueError,UnicodeError):
            raise HTTPException(503,'服务器 API Key 加密配置无效')
    if os.getenv('APP_ENV','development').lower() == 'production':
        raise HTTPException(503,'正式环境必须配置独立的 AI_KEY_ENCRYPTION_KEY')
    key_path = get_database_path().parent / '.ai-credential-encryption.key'
    key_path.parent.mkdir(parents=True,exist_ok=True)
    if not key_path.exists():
        try:
            fd = os.open(key_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'wb') as output:
                output.write(Fernet.generate_key())
        except FileExistsError:
            pass
    try:
        return Fernet(key_path.read_bytes())
    except (OSError,ValueError):
        raise HTTPException(503,'无法读取个人 API Key 加密配置')


def key_status(account_id):
    with get_connection() as db:
        row = db.execute('SELECT model,updated_at FROM personal_ai_keys WHERE account_id=?',(account_id,)).fetchone()
    return {'bound':bool(row),'model':row['model'] if row else 'qwen-plus','updated_at':row['updated_at'] if row else None}


def provider_key(account_id):
    with get_connection() as db:
        row = db.execute('SELECT encrypted_key,model FROM personal_ai_keys WHERE account_id=?',(account_id,)).fetchone()
    if not row:
        raise HTTPException(409,'请先到个人中心绑定自己的百炼 API Key')
    try:
        return cipher().decrypt(row['encrypted_key'].encode()).decode(),row['model']
    except InvalidToken:
        raise HTTPException(503,'个人 API Key 无法解密，请联系管理员恢复加密配置或重新绑定')


class KeyInput(BaseModel):
    api_key: SecretStr
    model: str = 'qwen-plus'
    free_only_confirmed: bool = False


def create_key_router(require_roles):
    router = APIRouter(prefix='/api/v1/ai',tags=['个人千问 API 配置'])
    users = require_roles('student','teacher')

    @router.get('/key')
    def status(user=Depends(users)):
        return key_status(user['account_id'])

    @router.put('/key')
    def bind(payload: KeyInput,user=Depends(users)):
        secret = payload.api_key.get_secret_value().strip()
        if not re.fullmatch(r'sk-[A-Za-z0-9_.-]{8,500}',secret):
            raise HTTPException(422,'请输入有效格式的百炼 API Key；不要填写账号密码')
        if not re.fullmatch(r'qwen-[a-zA-Z0-9._-]{1,90}',payload.model):
            raise HTTPException(422,'模型名称必须是有效的 qwen 模型编号')
        if not payload.free_only_confirmed:
            raise HTTPException(422,'请先确认已在百炼为所选模型开启免费额度用完即停')
        encrypted = cipher().encrypt(secret.encode()).decode()
        with get_connection() as db:
            db.execute('INSERT INTO personal_ai_keys VALUES (?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET '
                       'encrypted_key=excluded.encrypted_key,model=excluded.model,updated_at=excluded.updated_at',
                       (user['account_id'],encrypted,payload.model,utc_now()))
        # Binding is local only; no validation request can consume the user's quota.
        record_event(user,'ai.key_bound',{'model':payload.model})
        return key_status(user['account_id'])

    @router.delete('/key',status_code=204)
    def unbind(user=Depends(users)):
        with get_connection() as db:
            db.execute('DELETE FROM personal_ai_keys WHERE account_id=?',(user['account_id'],))
        record_event(user,'ai.key_removed')

    return router


async def chat(user,message,conversation_id=None,attempt_id=None,course_id=None):
    account = str(user['account_id'])
    task = get_attempt(user,attempt_id) if attempt_id else None
    if task:
        if task['account_id'] != account:
            raise HTTPException(403,'只能在自己的做题会话中提问')
        course_id = task['course_id']
    elif course_id:
        require_course(user,course_id)
    secret,model = provider_key(account)
    with get_connection() as db:
        db.execute('BEGIN IMMEDIATE')
        linked = db.execute('SELECT conversation_id FROM conversation_tasks WHERE account_id=? AND attempt_id=?',(account,attempt_id)).fetchone() if attempt_id else None
        if linked:
            conversation_id = linked[0]
        elif conversation_id:
            if not conversation_belongs_to_account(conversation_id,account):
                raise HTTPException(404,'会话不存在')
            context = db.execute('SELECT attempt_id,course_id FROM conversation_tasks WHERE conversation_id=?',(conversation_id,)).fetchone()
            if context and (context['attempt_id'] != attempt_id or context['course_id'] != course_id):
                raise HTTPException(409,'会话不属于当前习题或课程')
            if not context:
                db.execute('INSERT INTO conversation_tasks VALUES (?,?,?,?)',(conversation_id,account,attempt_id,course_id))
        else:
            conversation_id = str(uuid4())
            stamp = utc_now()
            db.execute('INSERT INTO conversations VALUES (?,?,?,?,?)',(conversation_id,account,message[:60],stamp,stamp))
            db.execute('INSERT INTO conversation_tasks VALUES (?,?,?,?)',(conversation_id,account,attempt_id,course_id))
    previous = list_messages(conversation_id,account)[-20:]
    save_message(conversation_id,account,'user',message)
    messages = [{'role':'system','content':'你是知序平台的千问聊天助手。请清晰准确地回答用户的问题，不确定时说明。用户可以自由提问。'}]
    if task:
        messages.append({'role':'system','content':'当前课堂习题：'+task['task']['title']+'\n'+task['task']['instructions']})
    messages.extend({'role':item['role'],'content':item['content']} for item in previous)
    messages.append({'role':'user','content':message})
    request_id = str(uuid4())
    record_event(user,'ai.sent',{'request_id':request_id,'conversation_id':conversation_id,'message':message,'model':model},attempt_id,course_id)
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60,trust_env=False) as client:
            result = await client.post(QWEN_URL,headers={'Authorization':f'Bearer {secret}'},
                                       json={'model':model,'messages':messages,'stream':False,'max_tokens':1600})
        if result.is_error:
            status = result.status_code
            error = '千问请求失败，请检查个人 Key、模型权限和账户状态'
            if status == 401:
                error = '个人百炼 API Key 无效或已撤销，请重新绑定'
            elif status == 403:
                error = '千问拒绝调用：请检查所选模型免费额度是否到期、用尽或没有访问权限；平台不会切换到其他账号'
            elif status == 429:
                error = '千问当前调用过于频繁，请稍后再试'
            raise HTTPException(502 if status >= 500 else status,error)
        body = result.json()
        answer = body['choices'][0]['message']['content']
        if not isinstance(answer,str) or not answer:
            raise ValueError('Invalid provider response')
    except (httpx.RequestError,ValueError,KeyError,IndexError,HTTPException) as exc:
        wait_ms = round((time.perf_counter()-started)*1000)
        record_event(user,'ai.failed',{'request_id':request_id,'conversation_id':conversation_id,'wait_ms':wait_ms,
                                     'status':exc.status_code if isinstance(exc,HTTPException) else 502},attempt_id,course_id)
        if isinstance(exc,HTTPException):
            raise exc
        raise HTTPException(502,'暂时无法连接千问或回复格式无效，请稍后重试') from None
    saved = save_message(conversation_id,account,'assistant',answer)
    record_event(user,'ai.replied',{'request_id':request_id,'conversation_id':conversation_id,'content':answer,
                                  'model':model,'wait_ms':round((time.perf_counter()-started)*1000),'usage':body.get('usage',{})},attempt_id,course_id)
    return {'response':answer,'model':model,'conversation_id':conversation_id,'created_at':saved['created_at']}
