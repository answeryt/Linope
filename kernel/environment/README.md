# environment

`KernelEnvironment` 是一个能力进程看到的房间，由资源记录上的租约配出来。房间里有这些门：

- `shell`：工作目录和经筛选的环境；
- `policy`：这次启动的宿主限制；
- `filesystem`：允许访问的路径；
- `file_io`：带路径边界检查的文件读写；
- `identity`：进程身份和按名读取密钥；
- `compute`：外部命令准入、超时和沙箱包装；
- `lifecycle`：合作式停止和生命周期限制。

目录边界和读写档位在 `mount.py`：只读、工作区可写、完全放开。档位来自沙箱申请里的 `mode`。这是房间规矩，不是资源池里的一种资源。

通信由 `kernel/communication` 负责，内存页面和句柄由 `kernel/resource` 负责，环境不再复制这两套状态。权限在启动时从资源记录得出，运行时不动态 widening。
