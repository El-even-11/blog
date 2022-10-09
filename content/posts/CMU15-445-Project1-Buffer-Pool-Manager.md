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

其中 `Extendible Hash Table` 和 `LRU-K Replacer` 是 `Buffer Pool Manager` 内部的组件，而 `Buffer Pool Manager` 则是向系统提供了获取 page 的接口。系统拿着一个 `page_id` 就可以向 `Buffer Pool Manager` 索要对应的 page，而不关心这个 page 具体存放在哪。系统并不关心（也不可见）获取这个 page 的过程，无论是从 disk 还是 memory 上读取，还是 page 可能发生的在 disk 和 memory 间的移动。这些内部的操作交由 `Buffer Pool Manager` 完成。

![](../../imgs/15-445-1-1.png)

`Disk Manager` 已经为我们提供，是实际在 disk 上读写数据的接口。

## Extendible Hash Table

### Extendible Hash Table Design

这个部分要实现一个 extendible 哈希表，内部不可以用 built-in 的哈希表，比如 `unordered_map`。这个哈希表在 Buffer Pool Manager 中主要用来存储 buffer pool 中 page id 和 frame id 的映射关系。

Extendible Hash Table 由一个 directory 和多个 bucket 组成。

- **directory**: 存放指向 bucket 的指针，是一个数组。用于寻找 key 对应 value 所在的 bucket。
- **bucket**: 存放 value，是一个链表。一个 bucket 可以至多存放指定数量的 value。

Extendible Hash Table 与 Chained Hash Table 最大的区别是，Extendible Hash 中，不同的指针可以指向同一个 bucket，而 Chained Hash 中每个指针对应一个 bucket。

发生冲突时，Chained Hash 简单地将新的 value 追加到其 key 对应 bucket 链表的最后，也就是说 Chained Hash 的 bucket 没有容量上限。而 Extendible Hash 中，如果 bucket 到达容量上限，则对桶会进行一次 split 操作。

在介绍 split 之前，我们先介绍一下 Extendible Hash 的插入流程。

将一个键值对 (K,V) 插入哈希表时，会先用哈希函数计算 K 的哈希值 H(K)，并用此哈希值计算出索引，将 V 放入索引对应的 bucket 中。

Extendible Hash 计算索引的方式是直接取哈希值 H(K) 的低 n 位。在这里，我们把 n 叫做 global depth。例如，K 对应的 H(K) = 1010 0010b，此时 global depth 为 4，则对应的 index 为 0010，即应将 V 放入 directory 里 index 为 2 的指针指向的 bucket 中。

global depth 的初始值为 0，取 H(K) 的低 0 位为索引，永远为 0，即初始时只有一个 bucket。

![](../../imgs/15-445-1-2.png)

我们指定 bucket 的容量为 2，现在向表中插入 KV 对。方便起见，就不具体指明 V 的值了，仅关注 K。K 从 0 递增，并且假设 H(K) = K。

首先插入 0 和 1。由于 global depth 为 0，所以 H(K) 计算出的 index 均为 0：

![](../../imgs/15-445-1-3.png)

再插入 2。index 仍然为 0。而此时 bucket 已满，无法继续插入 2，则需要进行之前提到的 split 操作。这时的 split 包含如下几个步骤：

1. global depth++
2. directory 容量翻倍
3. 创建一个新的 bucket
4. 重新安排指针
5. 重新分配 KV 对

流程如下：

![](../../imgs/15-445-1-4.png)

到目前为止应该还是比较容易理解的。global depth++ 后为 1，需要取 H(K) 的低 1 位作为 index，index 就有了 0 1 之分。因此 dir 拥有的指针数需要翻倍。仅仅是 index 数量翻倍还不够，此时 0 和 1 仍然指向同一个 bucket，仍然没有空间插入新值，因此还需要新创建一个 bucket。创建 bucket 后，自然需要将 dir 指针重新安排，0 指向 bucket 0，1 指向 bucket 1。

为什么 KV 对也需要重新分配？假设不重新分配 KV 对，现在有一个 find 请求，查找 K=1 对应的 V。H(K)=1，global depth=1，则 index=1。而此时 index=1 对应的 bucket 空空如也。

因此为了保证原数据与新的表结构兼容，需要重新计算发生 split 的 bucket，即 bucket 0 中所有 KV 对的新位置，并重新分配。

现在，我们就有了合适的位置来插入 2：

![](../../imgs/15-445-1-5.png)

接下来我们尝试插入 4。global depth 为 1，H(K)= 100b，index=0。而 index=0 指向的 bucket 又满了，再对 bucket 0 进行一次 split：

![](../../imgs/15-445-1-6.png)

到这里就体现了 Extendible Hash 特殊之处：多个 index 可以指向同一个 bucket。为了支持这种特性，要引入一个新的变量，local depth。

每个 bucket 都有一个自己的 local depth。bucket 实际上只用到了 H(K) 的低 local depth 位作为索引。local depth 的初始值为 0。在 bucket 发生 split 时，local depth++：

![](../../imgs/15-445-1-7.png)

bucket 0 和 bucket 2 的 local depth 均为 2，即他们实际上都用到了 H(K) 的低 2 位作为 index。例如，H(0)=00b，H(2)=10b，则 0 和 2 对应的 index 分别为 0 和 2，实际上也被分配在了 bucket 0 和 2。

bucket 1 的 local depth 为 1，其中存放的值实际上只用到了 H(K) 的低 1 位。例如 H(1)=01b，H(3)=11b，index 分别为 1 和 3，但实际上只用到了低 1 位，均为 1，因此 1 和 3 均被放在 bucket 1 中。

经过第 2 次 split，我们有了放入 4 的空间。H(4)=100b，global depth=2，index=0，即 4 被放入 dir[0] 对应的 bucket 0 中。

插入 3，成功插入到 bucket 1 中。

再插入 5。此时 bucket 1 已满，需要对 bucket 1 进行 split。但我们可以发现，这次插入并不需要将 dir 的容量翻倍，仅需新建一个 bucket 3，将 index 3 对应指针指向 bucket 3，并将原 bucket 1 中的 KV 对重新分配到 bucket 1 和 bucket 3 中：

![](../../imgs/15-445-1-8.png)

也就是说，当 bucket 需要分裂时，如果此时已经有多个指针指向 bucket，无需对 dir 进行扩容，仅执行原 5 步中的第 3、4、5 步。在代码中的体现就是，当需要插入 K 时，发现 bucket 已满，首先判断当前 bucket 的 local depth 是否等于 global depth：

- 若相等，即仅有一个指针指向 bucket，需要对 dir 扩容。
- 若不相等，即有多个指针指向 bucket，则无需扩容，将原来指向此 bucket 的指针重新分配。

现在还剩下几个关键的问题：

- dir 扩容时，新的指针应该指向哪里？
  假如 global depth=2，原索引为 000b 001b 010b 011b，则扩容添加的索引为 100b 101b 110b 111b，可以看出低两位的值是一一对应的，新索引应指向低位对应索引的 bucket。我们把指向同一个 bucket 的指针称为兄弟指针。

- 如何重新安排指针？
  重新安排指针实际上是重新安排指向需要 split 的 bucket 的兄弟指针。需要注意的是，兄弟指针不一定只有两个，而可以有 2^n 次个。例如下面这种情况：

  ![](../../imgs/15-445-1-9.png)

  当我们插入 0 1 3 5 9 时，就会出现这种情况，其中 bucket 0 共有 2^2 个兄弟指针。实际上，兄弟指针的个数为 2^(global depth - local depth)。那么得知一个 index 后，如何找到这个 index 所有兄弟指针？仍然以上面为例。插入 2，插入至 bucket 0，再插入 4，bucket 0 已满，进行一次 split。H(4) = 100b，对应 index 是 4。因此需要找到 index 4 的所有兄弟指针。bucket 0 的 local depth 为 1，即只用到了低 1 位。100b 的低 1 位为 0。那么其兄弟指针的低 1 位也应是 0，即 000b 010b 100b 110b，分别为 0 2 4 6。这样我们就找到了所有的兄弟指针。接下来将兄弟指针重新分配。local depth 变为 2，用到低 2 位，则兄弟指针可以分为两组，x00b 和 x10b，即 0 4 一组，2 6 一组。其中，一组指向原 bucket 0，另一组指向新 bucket 4。这样就完成了指针的重新分配。
  其他情况也是类似的，先通过低位相同的特征找到所有兄弟指针，再将兄弟指针按照新位是 0 还是 1 分为两组，分别指向原 bucket 和新 bucket。

- 如何重新分配 KV 对？
  仅需用 global depth 重新计算一遍 K 对应的 index 并插入对应 bucket。

到这里 Extendible Hash Table 就介绍完毕了。接下来说几个实现上的小细节。

### Extendible Hash Table Implementation

Extendible Hash Table 是要保证线程安全的。目前我的策略是一把大锁报平安。这样做多线程的性能肯定是很糟的。实际上应该是整个 table 一把大锁，再分区加多把小锁，或者更简单的做法，每个 bucket 一把小锁。均使用读写锁。

对于每个 bucket，在 Find 时上读锁，Insert 和 Remove 时上写锁。

对于整张表，Find 和 Remove 时上读锁。Find 上读锁好理解，而 Remove 实际上只会改变 bucket 的内部变量，其线程安全由 bucket 内部锁保证，因此也可以只上读锁。Insert 在无需 split 时也可以仅上读锁，需要 split 时上写锁。

我按照这个思路尝试优化了一下，结果成功负优化。可能是哪里出了点问题，有空再回头看看。先一把大锁凑合用。

另一个小细节是，每次 Insert 前要判断一下是否需要 split。而 split 之后不一定代表可以直接 Insert，因为可能重新分配 KV 对时，所有的 KV 对又被塞到了同一个 bucket 里，而凑巧的是需要插入的 KV 对也被带到了这个 bucket。因此需要循环判断，可能需要多次 split 才能成功插入。

## LRU-K Replacer

### LRU-K Replacer Design

LRU-K Replacer 用于存储 buffer pool 中 page 被引用的记录，并根据引用记录来选出在 buffer pool 满时需要被驱逐的 page。

LRU 应该都比较熟悉了，LRU-K 则是一个小小的变种。

在普通的 LRU 中，我们仅需记录 page 最近一次被引用的时间，在驱逐时，选择最近一次引用时间最早的 page。

在 LRU-K 中，我们需要记录 page 最近 K 次被引用的时间。假如 list 中所有 page 都被引用了大于等于 K 次，则比较最近第 K 次被引用的时间，驱逐最早的。假如 list 中存在引用次数少于 K 次的 page，则将这些 page 挑选出来，用普通的 LRU 来比较这些 page 第一次被引用的时间，驱逐最早的。

![](../../imgs/15-445-1-10.png)

另外还需要注意一点，LRU-K Replacer 中的 page 有一个 evictable 属性，当一个 page 的 evicitable 为 false 时，上述算法跳过此 page 即可。这里主要是为了上层调用者可以 pin 住一个 page，对其进行一些读写操作，此时需要保证 page 驻留在内存中。

LRU-K 的算法还是比较简单的，主要看具体实现部分。

### LRU-K Replacer Implementation

先是线程安全，LRU-K Replacer 的线程安全似乎并没有什么可以优化的地方，直接加一把大锁就可以了。

传统的 LRU 用哈希表加双向链表实现，可以保证各操作均为 O(1) 的复杂度。由于 LRU-K 需要保存 K 次引用的记录，就不能再用双向链表了。

先介绍一下 frame 的概念。page 放置在 buffer pool 的 frame 中，frame 的数量是固定的，即 buffer pool 的大小。如果 buffer pool 中的一个 frame 没有用来放置任何 page，则说该 frame 是空闲的。如果所有 frame 都不是空闲的，则表明 buffer pool 已满。

Replacer 里有一张哈希表，用于存储不同 frame 的信息。将 frame 的信息封装成 `FrameInfo ` 类。哈希表的 key 为 frame id，value 为 FrameInfo。

FrameInfo 里用链表保存 page 最近 K 次被引用的时间戳。这里的时间戳不适合也不需要用真正的 Unix 时间戳，直接用一个从 0 递增的 `size_t` 变量 `curr_timestamp` 来表示即可，每次引用 Replacer 中的任一 page 时，记录该次引用的时间戳为 `curr_timestamp`，并将其加 1。`size_t` 的大小也保证了这个变量不会溢出。

后续的实现比较简单，按照 LRU-K 算法的逻辑简单遍历查找最早的访问时间戳即可。

evictable 等变量的变化比较简单，按照文档来就可以，这里就不再多说了。

## Buffer Pool Manager Instance

### Buffer Pool Manager Design

这个部分的代码不是很难，主要是需要理清各个函数的作用和关系。

Buffer Pool Manager 里有几个重要的成员：

- pages：buffer pool 中缓存 pages 的指针数组
- disk_manager：框架提供，可以用来读取 disk 上指定 page id 的 page 数据，或者向 disk 上给定 page id 对应的 page 里写入数据
- page_table：刚才实现的 Extendible Hash Table，用来将 page id 映射到 frame id，即 page 在 buffer pool 中的位置
- replacer：刚才实现的 LRU-K Replacer，在需要驱逐 page 腾出空间时，告诉我们应该驱逐哪个 page
- free_list：空闲的 frame 列表

Buffer Pool Manager 给上层调用者提供的两个最重要的功能是 new page 和 fetch page。我们先理一理 Buffer Pool Manager 完成这两项工作的流程：

**New Page**

上层调用者希望新建一个 page，调用 `NewPgImp`。

如果当前 buffer pool 已满并且所有 page 都是 unevictable 的，直接返回。否则：

- 如果当前 buffer pool 里还有空闲的 frame，创建一个空的 page 放置在 frame 中。
- 如果当前 buffer pool 里没有空闲的 frame，但有 evitable 的 page，利用 LRU-K Replacer 获取可以驱逐的 frame id，将 frame 中原 page 驱逐，并创建新的 page 放在此 frame 中。驱逐时，
  - 如果当前 frame 为 dirty(发生过写操作)，将对应的 frame 里的 page 数据写入 disk，并重置 dirty 为 false。清空 frame 数据，并移除 page_table 里的 page id，移除 replacer 里的引用记录。
  - 如果当前 frame 不为 dirty，直接清空 frame 数据，并移除 page_table 里的 page id，移除 replacer 里的引用记录。

在 replacer 里记录 frame 的引用记录，并将 frame 的 evictable 设为 false。因为上层调用者拿到 page 后可能需要对其进行读写操作，此时 page 必须驻留在内存中。

使用 `AllocatePage` 分配一个新的 page id(从0递增)。

将此 page id 和存放 page 的 frame id 插入 page_table。

page 的 pin_count 加 1。

**Fetch Page**

上层调用者给定一个 page id，Buffer Pool Manager 返回对应的 page 指针。调用 `FetchPgImp`。

假如可以在 buffer pool 中找到对应 page，直接返回。

否则需要将磁盘上的 page 载入内存，也就是放进 buffer pool。

如果当前 buffer pool 已满并且所有 page 都是 unevictable 的，直接返回空指针。否则同 New Page 操作，先尝试在 free list 中找空闲的 frame 存放需要读取的 page，如果没有 frame 空闲，就驱逐一张 page。获得一个空闲的 frame。

通过 disk_manager 读取 page id 对应 page 的数据，存放在 frame 中。在 replacer 里记录引用，将 evictable 设为 false，将 page id 插入 page_table，page 的 pin_count 加 1。

流程还是比较简单的，总的来说就是 buffer pool 里没空位也腾不出空位，直接返回，暂时处理不了请求，如果有空位，就先用空位，没空位但可以驱逐，就驱逐一个 page 腾出空位。这样就可以在内存中缓存一个 page 方便上层调用者操作。同时，还需要同步一些信息，比如 page_table 和 replacer，驱逐 page 时，如果是 dirty page 也需要先将其数据写回 disk。

![](../../imgs/15-445-1-11.png)

接下来说说 pin 和 unpin。

当上层调用者新建一个 page 或者 fecth 一个 page 时，Buffer Pool Manager 会自动 pin 一下这个 page。接下来上层调用者对这个 page 进行一系列读写操作，操作完之后调用 unpin，告诉 Buffer Pool Manager，这个 page 我用完了，你可以把它直接丢掉或者 flash 掉了（也不一定真的可以，可能与此同时有其他调用者也在使用这个 page，具体能不能 unpin 掉要 Buffer Pool Manager 在内部判断一下 page 的 pin_count 是否为 0）。调用 unpin 时，同时传入一个 `is_dirty` 参数，告诉 Buffer Pool Manager 我刚刚对这个 page 进行的是读操作还是写操作。需要注意的是，Buffer Pool Manager 不能够直接将 page 的 dirty flag 设为 is_dirty。假设原本 dirty flag 为 true，则不能改变，代表其他调用者进行过写操作。只有原本 dirty flag 为 false 是，才能将 dirty flag 直接设为 is_dirty。

整个流程大概就是这样。把流程理清楚，注意一些变量的同步，还是比较简单的。

## Summary

整个 project 1 难度不算大，coding + debugging 时间大概是 4 个小时左右。个人感觉难度最大的部分是 Extendible Hash Table，因为要进行一些比较 trick 的位运算操作，我是真的有点玩不转。Buffer Pool Manager 部分的流程比较复杂，细节比较多，但认真按注释编写应该不会有什么问题。

由于所有数据结构都是粗暴的一把大锁锁住，代码的性能不尽如人意，这里留个坑，之后有机会优化一下。


