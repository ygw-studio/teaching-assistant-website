import math


class min_stack:
    def __init__(self):
        self.stack = SqStack(50)
        self.min_stack = SqStack(50)
        self.min_stack.push(math.inf)
    def push(self,x):
        self.stack.push(x)
        self.min_stack.push(min(x, self.min_stack.peek()))
    def pop(self):
        self.min_stack.pop()
        return self.stack.pop()
    def top(self):
        return self.stack.peek()
    def getMin(self):
        return self.min_stack.peek()
