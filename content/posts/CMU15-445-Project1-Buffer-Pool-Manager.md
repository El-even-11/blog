---
title: "CMU15-445 Project1 Buffer Pool Manager"
date: 2022-10-08T22:11:18+08:00
# weight: 1
# aliases: ["/first"]
tags: ["Database"]
author: "Me"
# author: ["Me", "You"] # multiple authors
showToc: true
TocOpen: true
draft: false
hidemeta: false
comments: false
description: "Implement Buffer Pool Manager for CMU BUSTUB"
canonicalURL: "https://canonical.url/to/page"
disableHLJS: true # to disable highlightjs
disableShare: false
disableHLJS: false
hideSummary: false
searchHidden: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowPostNavLinks: true
ShowWordCount: true
ShowRssButtonInSectionTermList: true
UseHugoToc: true
cover:
    image: "<image path/url>" # image path/url
    alt: "<alt text>" # alt text
    caption: "<text>" # display caption under cover
    relative: false # when using page bundles set this to true
    hidden: true # only hide on current single page
editPost:
    URL: "https://github.com/el-even-11/blog/content"
    Text: "Suggest Changes" # edit text
    appendFilePath: true # to append file path to Edit link
---

暂时战略放弃了 6.824 的 Lab4，来做做 CMU 新鲜出炉的 [15-445 FALL 2022](https://15445.courses.cs.cmu.edu/fall2022)。

## Resources
- [https://15445.courses.cs.cmu.edu/fall2022](https://15445.courses.cs.cmu.edu/fall2022) 课程官网
- [https://github.com/cmu-db/bustub](https://github.com/cmu-db/bustub) Bustub Github Repo
- [https://www.gradescope.com/](https://www.gradescope.com/) 自动测评网站 GradeScope，course entry code: PXWVR5
- [https://discord.gg/YF7dMCg](https://discord.gg/YF7dMCg) Discord 论坛，课程交流用
- bilibili 有搬运的课程视频，自寻。

**请不要将实现代码公开，尊重 Andy 和 TAs 的劳动成果！**

## Set up Environment
实验需要 Linux 环境。虽说 Docker 什么的似乎也可以，但 Linux 总是更令人安心。为了方便测试，我选择了云服务器。

JetBrains 家推出了新的 SSH 远程开发功能。本来想试试，结果 CLion 在 server 上足足吃了两三个 G 的内存，我 2 核 4G 的服务器不堪重负，还是老老实实用 vscode remote。

Debug 推荐用 lldb，在 vscode 安装相关插件后体验很好。终于不用整天翻看 6.824 又臭又长的 log 了。

## Overview
Project1 主要与 Bustub 的 storage manager 相关，分为三个部分：

- Extendible Hash Table
- LRU-K Replacer
- Buffer Pool Manager Instance

其中 `Extendible Hash Table` 和 `LRU-K Replacer` 是 `Buffer Pool Manager` 内部的组件，而 `Buffer Pool Manager` 则是向系统提供了获取 page 的接口。系统拿着一个 `page_id` 就可以向 `Buffer Pool Manager` 索要对应的 page，而不关心这个 page 具体存放在哪。而系统并不关心（也不可见）获取这个 page 的过程，无论是从 disk 还是 memory 上读取，还是 page 可能发生的在 disk 和 memory 间的移动。这些内部的操作交由 `Buffer Pool Manager` 完成。

![](../../imgs/15-445-1-1.png)

`Disk Manager` 已经为我们提供，是实际在 disk 上读写数据的接口。

## Extendible Hash Table
这个部分要实现一个 extendible 哈希表，内部不可以用 built-in 的哈希表，比如 `unordered_map`。

Extendible Hash Table 主要由一个 directory 和多个 bucket 组成。
- **directory**: 存放指向 bucket 的指针，是一个数组。用于寻找 key 对应 value 所在的 bucket。
- **bucket**: 存放 value，是一个链表。一个 bucket 可以至多存放指定数量的 value。

Extendible Hash Table 与 Chained Hash Table 最大的区别是，Extendible Hash 中，不同的指针可以指向同一个 bucket，而 Chained Hash 中每个指针对应一个 bucket。

发生冲突时，Chained Hash 简单地将新的 value 追加到其 key 对应 bucket 链表的最后，也就是 Chained Hash 的 bucket 没有容量上限。而 Extendible Hash 中，如果 bucket 到达容量上限，则会进行一次 split 操作。

在介绍 split 之前，需要先介绍另外两个概念：global depth 和 local depth。