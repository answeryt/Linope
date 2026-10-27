"""Self-contained red-black tree implementation (insertion, deletion, search, inorder).

Node colors are the booleans RED=True / BLACK=False. The nil sentinel is a
single shared black node so that every real node has real children and no
None-checks are needed during fix-ups.
"""

RED = True
BLACK = False


class Node:
    __slots__ = ("key", "color", "left", "right", "parent")

    def __init__(self, key=None, color=BLACK, nil=None):
        self.key = key
        self.color = color
        self.left = nil
        self.right = nil
        self.parent = nil

    def __repr__(self):
        return "Node(%r, %s)" % (self.key, "RED" if self.color else "BLACK")


class RedBlackTree:
    def __init__(self):
        self.nil = Node(key=None, color=BLACK)
        self.nil.left = self.nil.right = self.nil.parent = self.nil
        self.root = self.nil
        self.size = 0

    # ---------- queries ----------

    def is_empty(self):
        return self.size == 0

    def __len__(self):
        return self.size

    def __contains__(self, key):
        return self.find(key) is not None

    def find(self, key):
        node = self.root
        while node is not self.nil:
            if key == node.key:
                return node
            node = node.left if key < node.key else node.right
        return None

    def minimum(self, node=None):
        node = self.root if node is None else node
        if node is self.nil:
            return None
        while node.left is not self.nil:
            node = node.left
        return node

    def maximum(self, node=None):
        node = self.root if node is None else node
        if node is self.nil:
            return None
        while node.right is not self.nil:
            node = node.right
        return node

    def inorder(self):
        """Return all keys in ascending order."""
        out, stack, node = [], [], self.root
        while stack or node is not self.nil:
            while node is not self.nil:
                stack.append(node)
                node = node.left
            node = stack.pop()
            out.append(node.key)
            node = node.right
        return out

    def height(self):
        """Black-height plus red count, computed by a simple recursive walk."""
        def walk(node):
            if node is self.nil:
                return 0
            return 1 + max(walk(node.left), walk(node.right))
        return walk(self.root)

    # ---------- rotations ----------

    def _left_rotate(self, x):
        y = x.right
        x.right = y.left
        if y.left is not self.nil:
            y.left.parent = x
        y.parent = x.parent
        if x.parent is self.nil:
            self.root = y
        elif x is x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y

    def _right_rotate(self, y):
        x = y.left
        y.left = x.right
        if x.right is not self.nil:
            x.right.parent = y
        x.parent = y.parent
        if y.parent is self.nil:
            self.root = x
        elif y is y.parent.right:
            y.parent.right = x
        else:
            y.parent.left = x
        x.right = y
        y.parent = x

    # ---------- insertion ----------

    def insert(self, key):
        """Insert key. Returns False if the key is already present."""
        parent, node = self.nil, self.root
        while node is not self.nil:
            if key == node.key:
                return False
            parent = node
            node = node.left if key < node.key else node.right
        new = Node(key=key, color=RED, nil=self.nil)
        new.parent = parent
        new.left = new.right = self.nil
        if parent is self.nil:
            self.root = new
        elif key < parent.key:
            parent.left = new
        else:
            parent.right = new
        self.size += 1
        self._insert_fixup(new)
        return True

    def _insert_fixup(self, z):
        while z.parent.color is RED:
            grand = z.parent.parent
            if z.parent is grand.left:
                uncle = grand.right
                if uncle.color is RED:
                    z.parent.color = BLACK
                    uncle.color = BLACK
                    grand.color = RED
                    z = grand
                else:
                    if z is z.parent.right:
                        z = z.parent
                        self._left_rotate(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._right_rotate(z.parent.parent)
            else:
                uncle = grand.left
                if uncle.color is RED:
                    z.parent.color = BLACK
                    uncle.color = BLACK
                    grand.color = RED
                    z = grand
                else:
                    if z is z.parent.left:
                        z = z.parent
                        self._right_rotate(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._left_rotate(z.parent.parent)
        self.root.color = BLACK

    # ---------- deletion ----------

    def _transplant(self, u, v):
        if u.parent is self.nil:
            self.root = v
        elif u is u.parent.left:
            u.parent.left = v
        else:
            u.parent.right = v
        v.parent = u.parent

    def delete(self, key):
        """Delete key. Returns False if the key is not present."""
        z = self.find(key)
        if z is None:
            return False
        y = z
        y_original_color = y.color
        if z.left is self.nil:
            x = z.right
            self._transplant(z, z.right)
        elif z.right is self.nil:
            x = z.left
            self._transplant(z, z.left)
        else:
            y = self.minimum(z.right)
            y_original_color = y.color
            x = y.right
            if y.parent is z:
                x.parent = y
            else:
                self._transplant(y, y.right)
                y.right = z.right
                y.right.parent = y
            self._transplant(z, y)
            y.left = z.left
            y.left.parent = y
            y.color = z.color
        self.size -= 1
        if y_original_color is BLACK:
            self._delete_fixup(x)
        self.nil.color = BLACK
        return True

    def _delete_fixup(self, x):
        while x is not self.root and x.color is BLACK:
            if x is x.parent.left:
                w = x.parent.right
                if w.color is RED:
                    w.color = BLACK
                    x.parent.color = RED
                    self._left_rotate(x.parent)
                    w = x.parent.right
                if w.left.color is BLACK and w.right.color is BLACK:
                    w.color = RED
                    x = x.parent
                else:
                    if w.right.color is BLACK:
                        w.left.color = BLACK
                        w.color = RED
                        self._right_rotate(w)
                        w = x.parent.right
                    w.color = x.parent.color
                    x.parent.color = BLACK
                    w.right.color = BLACK
                    self._left_rotate(x.parent)
                    x = self.root
            else:
                w = x.parent.left
                if w.color is RED:
                    w.color = BLACK
                    x.parent.color = RED
                    self._right_rotate(x.parent)
                    w = x.parent.left
                if w.left.color is BLACK and w.right.color is BLACK:
                    w.color = RED
                    x = x.parent
                else:
                    if w.left.color is BLACK:
                        w.right.color = BLACK
                        w.color = RED
                        self._left_rotate(w)
                        w = x.parent.left
                    w.color = x.parent.color
                    x.parent.color = BLACK
                    w.left.color = BLACK
                    self._right_rotate(x.parent)
                    x = self.root
        x.color = BLACK

    # ---------- invariants (used by the self-check below) ----------

    def check_invariants(self):
        """Raise AssertionError if any red-black property is violated."""
        assert self.root.color is BLACK, "root must be black"
        assert self.nil.color is BLACK, "nil must be black"

        def walk(node):
            if node is self.nil:
                return 1
            if node.color is RED:
                assert node.left.color is BLACK and node.right.color is BLACK, \
                    "red node %r has a red child" % (node.key,)
            if node.left is not self.nil:
                assert node.left.parent is node, "broken parent link"
            if node.right is not self.nil:
                assert node.right.parent is node, "broken parent link"
            left_black = walk(node.left)
            right_black = walk(node.right)
            assert left_black == right_black, \
                "black height mismatch at %r" % (node.key,)
            return left_black + (1 if node.color is BLACK else 0)

        walk(self.root)
        return True


if __name__ == "__main__":
    import random

    tree = RedBlackTree()
    values = list(range(200))
    random.shuffle(values)
    for v in values:
        tree.insert(v)
    assert tree.inorder() == list(range(200))
    tree.check_invariants()

    random.shuffle(values)
    for v in values:
        assert tree.delete(v)
        if v % 17 == 0:
            tree.check_invariants()
    assert tree.is_empty() and tree.root is tree.nil
    print("red-black tree: all checks passed")
