# address

工作区的地址空间。只列出这张 workspace 句柄映进来的文件页。

没有这张句柄，这一块是空的。页的状态仍用 [`../../memory/page.py`](../../memory/page.py)：`resident`、`pinned`、`swapped`。线程和这间屋子共享这些句柄，不另领一块地址空间。

- [`pages.py`](pages.py)：`mapped_pages` 按句柄挑出文件页。句柄是空的就什么都不返回。
