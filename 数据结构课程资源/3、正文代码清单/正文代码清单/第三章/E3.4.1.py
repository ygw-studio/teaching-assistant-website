class MyStack:
    def __init__(self):
        self.queue1 = SqQueue(50)
        self.queue2 = SqQueue(50)
    def push(self, x: int) -> None:
        self.queue2.offer(x)
        while not self.queue1.isEmpty():
            self.queue2.offer(self.queue1.poll())
        self.queue1, self.queue2 = self.queue2, self.queue1
    def pop(self) -> int:
        return self.queue1.poll()
    def top(self) -> int:
        return self.queue1.queueElem[self.queue1.front]
    def empty(self) -> bool:
        return self.queue1.isEmpty()
