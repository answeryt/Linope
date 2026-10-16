# memory

跟随并留下的表示，以及它们算不算进内存用量。这不是账本文件。账本在 [`../store/`](../store/README.md)。

没被跟随的目标不记表示。跟随并留下之后，正文还在或被钉住，篇幅才计入 [`../account/`](../account/README.md)。换出以后地址还在，只剩链接，用量不再加它。按页旁边的链接归到资源。

工作区那张句柄上的文件页见 [`../workspace/address/`](../workspace/address/README.md)。页的三种状态以这里为准。

- [`__init__.py`](__init__.py)：导出表示和任务类型。
- [`task_kind.py`](task_kind.py)：任务只有两类。不跟随是 `free`，只留链接。跟随并留下是 `occupy`。
- [`page.py`](page.py)：一份长期表示。地址、篇幅和状态。状态是 `resident`（正文还在）、`pinned`（钉住）、`swapped`（只剩链接）。`embedded` 在前两种时为真。
- [`file_page.py`](file_page.py)：为刚写好的文件做一份表示。地址用落盘路径，篇幅用字节数。需要长期留下时钉住，否则正文留在表示里。
