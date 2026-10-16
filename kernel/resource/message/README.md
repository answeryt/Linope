# message

往来正文。不是租来的设施，也不占用一种资源。

角色是 `user_msg`、`tool_msg`、`model_msg`、`system_msg`。`model_msg` 是模型说出来的话，不是模型租约。`system_msg` 是交给模型的规矩。组装说明的能力仍在 `capability/prompt`。发给模型厂家时，接口再译回 `user`、`assistant`、`tool`、`system`。

- [`message.py`](message.py)：角色枚举，以及一条带角色和正文的消息。
