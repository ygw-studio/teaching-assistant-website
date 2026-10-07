class MyQueue:
    def __init__(self):
        self.stack1=SqStack(50)
        self.stack2=SqStack(50)
    def move(self):
        while not self.stack1.isEmpty():
            self.stack2.push(self.stack1.pop())
    def push(self,x):
        self.stack1.push(x)
    def pop(self):
        if self.stack2.isEmpty():
            self.move()
        return self.stack2.pop()
    def peek(self):
        if self.stack2.isEmpty():
            self.move()
        return self.stack2.peek()
    def empty(self):
        return self.stack1.isEmpty() and self.stack2.isEmpty()
