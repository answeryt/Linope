# context

压缩能力的租约。这是一种设施，不是表示正文，也不等于内存用量。上下文占了多少，按所调模型的总窗口，在 [`../account/`](../account/README.md) 里算。

身份是能力号。调用参数不参与“是不是同一份”的编号。

- [`kind.py`](kind.py)：种类名 `context`。`identity` 要求能力号，空字符串会拒绝。
