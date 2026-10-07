class Node(object):
    def __init__(self, data=None, next=None):
        self.data = data
        self.next = next


class LinkList():
    def __init__(self):
        self.head = Node()


def mergeTwoLists(l1, l2):
    if l1 is None:
        return l2
    elif l2 is None:
        return l1
    elif l1.data < l2.data:
        l1.next = mergeTwoLists(l1.next, l2)
        return l1
    else:
        l2.next =mergeTwoLists(l1, l2.next)
        return l2
