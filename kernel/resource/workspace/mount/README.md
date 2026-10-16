# mount

工作区的挂载空间。碰文件的平级进程共享同一个项目根，各自再有一块私有临时目录。

家目录、`.git`、`.ssh`、`.aws` 和密钥文件不在视野里。进程自己读、写、改文件时，先走 `admit_path`：解析之后落到允许的根外面就拒绝，别人的私有临时目录也不能读不能写。句柄不对，或路径不在允许的根里，就拒绝。

- [`kind.py`](kind.py)：身份是项目根。`root_from` 从变更条款里读根，没有就用调用方给的后备路径。
- [`view.py`](view.py)：可读根、可写根，以及每个进程自己的临时目录。`admit_path` 做这一次判断。`blocked` 拒绝家目录本身、`.git`、`.ssh`、`.aws`、`.env`、`id_rsa`、`id_ed25519`、`credentials.json`，以及 `.pem`、`.key`、`.p12`、`.pfx`。
- [`mode.py`](mode.py)：`read-only` 只能读。`workspace-write` 可以改工作区。`danger-full-access` 只表示外部命令不包装。前两档要包装；选不出包装器就不跑。包装器在 `capability/sandbox`。
