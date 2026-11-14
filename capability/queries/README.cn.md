# queries

[English](README.md) | 中文

内核用单独进程来问的只读答案。内核不导入这些函数。

```text
python -m capability.queries tail-cut
```

标准输入是一个 JSON 对象：`messages`、整数 `budget`，以及等长的 `tokens`。标准输出是 `{"cut": <整数>}`。`cut` 是从末尾往前保留、直到用完 `budget` 时，第一个被留下的消息下标。`0` 表示全部装得下。
