# replica_layout

这个目录管编制：同一个能力该有哪几份进程在岗。它对比已经在跑的，给出要新开哪些、要关掉哪些。调和器按 `to_start` 把缺的那些份拉起来。

编号、份数、名字是三种算这份编制的规则。开发者按同一套接口登记自己的规则。调和器只按名字取出，不导入某一种布局的类。

没选布局时，一次启动仍是一份。这时在 `linope start` 末尾写大于 1 的份数会被拒绝。

选了 `numbered`、`counted` 或 `named` 之后，份数写在 `linope start` 末尾。不写就是 1。这个数字只用于这一次启动，不写进账本。账本只记住规则名字。`numbered` 仍用选中时保存的起点。`named` 用 `0` 到 `份数-1` 当这次的名字。开发者自己登记的规则不接受这个数字。

## 抽象层

大家只依赖 [layout.py](layout.py)。一种布局只要能回答两个问题，就可以接进来：

- `desired_replicas(capability, running)`：这个能力现在应该有哪些份。
- `plan_replicas(capability, running)`：对比已经在跑的，哪些要新开，哪些该关。

`capability` 是能力名，例如 `tools.bash`。`running` 是已经在跑的那些份，类型是 `Sequence[RunningReplica]`。前一个返回 `tuple[ReplicaSpec, ...]`，后一个返回 `ReplicaPlan`。

三样数据各自只带自己的字段：

- `ReplicaSpec`：还想要的一份。字段是 `capability`、`replica_name`、`label`、`process_id`。
- `RunningReplica`：已经在跑的一份。字段同上。
- `ReplicaPlan`：一张清单。`desired` 是对齐之后应该留下的，`to_start` 是要新开的，`to_stop` 是名单里已经没有、但还在跑的。

名字有固定写法。`make_replica(capability, label, process_id=None)` 把一份叫做 `能力名-label`。没给 `process_id` 时现造一个。已经在跑的那份要沿用它原来的 `process_id`，不要再造。`replica_label(capability, replica_name)` 取回 `能力名-` 后面的那段。

多数布局不用自己做对比。先写出想要的名单，再交给 `plan_from_desired(desired, running)`。同名且已在跑的留在 `desired` 里并沿用旧的 `process_id`；没在跑的放进 `to_start`；跑着但名单里没有的放进 `to_stop`。

登记和取出在 [registry.py](registry.py)，不在每一种布局里：

- `register_layout(name, layout)`：用一个名字记住这种布局。`off` 是保留名，不能登记。名字不能是空白。
- `unregister_layout(name)`：去掉后加的布局。`numbered`、`counted`、`named` 这三种内置的去不掉。
- `load_layout(name)`：按名字取出。没有这个名字会报 `KeyError`，并列出已知名字。对象若有 `isolated()`，这里返回它的一份拷贝，避免改设置时改到登记表里的那一个。
- `layout_names()`：按字母顺序列出已登记的名字。

下面三个方法不是非写不可。命令行和调和器发现有才调用：

- `isolated()`：返回一份互不影响的拷贝。没有它，`load_layout` 就返回登记表里的原对象。
- `default_settings()`：选中这个布局时记下的初始设置，是一个字典。
- `apply_settings(settings)`：启动前把记下的字典套到这份布局上。调和器只把保存下来的设置传进来，不关心字典里有哪些键。键由这种布局自己认。

开发者接入自己的方法时，写一个有上面两个必选方法的对象，调用 `register_layout("自己的名字", 那个对象)`。调和器之后只通过 `load_layout` 和 `plan_replicas` 使用它。

## 文件

- [__init__.py](__init__.py)：把共用的数据类型和登记函数集中导出。`ReplicaLayout`、`ReplicaPlan`、`ReplicaSpec`、`RunningReplica`、`layout_names`、`load_layout`、`register_layout`、`unregister_layout`。
- [layout.py](layout.py)：抽象层。数据类型、两个必选方法、起名和对比名单的公共函数都在这里。
- [registry.py](registry.py)：按名字登记和取出。内置三种在导入时登记好。

## numbered

固定编号。份数不变，空出来的号仍用原来的号补上。例如两份就是 `tools.bash-0`、`tools.bash-1`。

- [numbered/__init__.py](numbered/__init__.py)：这个子目录的标记，说明这里是固定编号。
- [numbered/expand.py](numbered/expand.py)：展开编号并实现 `NumberedLayout`。

`expand_numbered_replicas(capability, count, start=0, names=None)` 展开成若干 `ReplicaSpec`。`count` 至少为 1。不传 `names` 时，名字是从 `start` 起连续的编号。传入 `names` 时，个数必须等于 `count`；份数大于 1 时，每个名字必须是 `能力名-数字`，而且数字不能重复。

`NumberedLayout(count=2, start=0)` 忽略已经在跑的名单，每次都按这个固定范围重算。`default_settings()` 返回 `{"count": count, "start": start}`。`apply_settings` 认这两个键，`count` 小于 1 会拒绝。

## counted

只盯着份数。少了就补当前最小的空号，多了就关掉号最大的那几份。已经空掉的号视为不在，不会被当成还占着。

- [counted/__init__.py](counted/__init__.py)：这个子目录的标记，说明这里按目标份数对齐。
- [counted/count.py](counted/count.py)：算该补哪些号、该关哪些号，并实现 `CountedLayout`。

`next_replica_index(used)` 在一组已占用的整数里找最小的空号，从 0 起。

`reconcile_count(desired, running)` 的 `running` 是已经在用的编号。`desired` 至少为 1。返回 `(要新开的编号, 要关掉的编号)`。多于目标时只关号最大的多余份，不新开。少于目标时只补空号，不关。

`set_count(count, singleton)` 检查目标。小于 1 会拒绝。`singleton` 为真时，目标不能大于 1。`increase_count(count, singleton, step=1)` 和 `decrease_count(count, singleton, step=1)` 在这个检查上加减。

`CountedLayout(count=2, singleton=False)` 只把 `label` 是数字的在跑副本算进份数。`default_settings()` 返回 `{"count": count, "singleton": singleton}`。`apply_settings` 认这两个键。`set_count`、`increase_count`、`decrease_count` 改的是这一份布局自己的目标，并受 `singleton` 约束。

## named

按给定的名字开。一份新的是一个新名字，不是下一个编号。例如默认是 `alpha` 和 `beta`，进程名就是 `能力名-alpha`、`能力名-beta`。名单里没有、但还在跑的，会放进 `to_stop`。

- [named/__init__.py](named/__init__.py)：这个子目录的标记，说明这里按名字清单开关。
- [named/names.py](named/names.py)：按名字生成副本，并实现 `NamedLayout`。

`replicas_by_name(capability, names)` 每个名字一份。名字会转成字符串，重复会拒绝。

`diff_named_replicas(desired_names, running_names)` 返回 `(要新开的名字, 要关掉的名字)`，两边都按字母排序。它只比较名字，不生成 `ReplicaSpec`。

`NamedLayout(names=("alpha", "beta"))` 以这份名单为准，不根据已经在跑的去改名单。`default_settings()` 返回 `{"names": [...]}`。`apply_settings` 只在字典里有 `names` 时替换，替换后的名字不能重复。
