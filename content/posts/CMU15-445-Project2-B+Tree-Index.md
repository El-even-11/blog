---
title: "CMU15-445 Project2 B+Tree Index"
date: 2022-11-01T20:10:29+08:00
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
description: "Building a Concurrent B+Tree Index."
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

来记录一下 Bustub 噩梦 B+ 树的实现过程。

## Resources

- [https://15445.courses.cs.cmu.edu/fall2022](https://15445.courses.cs.cmu.edu/fall2022) 课程官网
- [https://github.com/cmu-db/bustub](https://github.com/cmu-db/bustub) Bustub Github Repo
- [https://www.gradescope.com/](https://www.gradescope.com/) 自动测评网站 GradeScope，course entry code: PXWVR5
- [https://discord.gg/YF7dMCg](https://discord.gg/YF7dMCg) Discord 论坛，课程交流用
- bilibili 有搬运的课程视频，自寻。

**请不要将实现代码公开，尊重 Andy 和 TAs 的劳动成果！**

## Overview
Project 2 需要为 Bustub 实现 B+ 树索引。拆分为两个部分：

- Checkpoint1: 单线程 B+ 树
- Checkpoint2: 多线程 B+ 树

实验中给出的 B+ 树接口非常简单，基本只有查询、插入和删除三个接口，内部基本没有给出别的辅助函数，可以让我们自由发挥（无从下手）。因此，任何合法的 B+ 树实现都是允许的。

B+ 树索引在 Bustub 中的位置如图所示：

![](../../imgs/15-445-2-1.png)

需要使用我们在 Project 1 中实现的 Buffer Pool Manager 来获取 Page。

## Checkpoint1 Single Thread B+Tree

Checkpoint1 分为两个部分：

- Task1: B+Tree Pages，B+树中的各种 Page。在 Bustub 索引 B+ 树中，所有的节点都是 Page。包含 Leaf Page，Internal Page ，和它们的父类 Tree Page。
- Task2：B+Tree Data Structure (Insertion, Deletion, Point Search)。Checkpoint1 的重点，即 B+树的插入、删除和单点查询。

### Task1: B+Tree Pages

Task1 的实现非常简单，都是一些普通的 Getter 和 Setter。这里主要介绍一下 Page 的内存布局。

在 Project 1 中我们第一次与 Page 打交道。Page 实际上可以存储数据库内很多种类的数据。例如索引和实际的表数据等等。

```cpp
/** The actual data that is stored within a page. */
char data_[BUSTUB_PAGE_SIZE]{};
/** The ID of this page. */
page_id_t page_id_ = INVALID_PAGE_ID;
/** The pin count of this page. */
int pin_count_ = 0;
/** True if the page is dirty, i.e. it is different from its corresponding page on disk. */
bool is_dirty_ = false;
/** Page latch. */
ReaderWriterLatch rwlatch_;
```

![](../../imgs/15-445-2-2.png)

其中，`data_` 是实际存放 Page 数据的地方，大小为 `BUSTUB_PAGE_SIZE`，为 4KB。其他的成员是 Page 的 metadata。

B+树 中的 Tree Page 数据均存放在 Page 的 data 成员中。

**B_PLUS_TREE_PAGE**

`b_plus_tree_page` 是另外两个 Page 的父类，即 B+树中 Tree Page 的抽象。

```cpp
IndexPageType page_type_;   // Leaf or Internal. 4 Byte
lsn_t lsn_  // temporarily unused. 4 Byte
int size_;  // tree page data size(not in byte, in count). 4 Byte
int max_size_;  // tree page data max size(not in byte, in count). 4 Byte
page_id_t parent_page_id_; // 4 Byte
page_id_t page_id_; // 4 Byte
// 24 Byte in total
```  

以上数据组成了 Tree Page 的 Header，即 metadata。

![](../../imgs/15-445-2-3.png)

Page Data 的 4KB 中，24Byte 用于存放 Header，剩下的则用于存放 Tree Page 的数据，即 KV 对。

**B_PLUS_TREE_INTERNAL_PAGE**

对应 B+ 树中的内部节点。

```cpp
MappingType array_[1];
```

Internal Page 中没有新的 metadata，Header 大小仍为 24B。它唯一的成员是这个怪怪的大小为 1 的数组。大小为 1 显然不合理，代表只能存放一个 KV 对。但又没法改变它的大小，难道要用 Undefined Behavior 来越界访问其后的地址？实际上差不多就是这个意思。但这不是 Undefined Behavior，是一种特殊的写法，叫做 flexible array。我也不知道怎么翻译。

简单来说就是，当你有一个类，这个类中有一个成员为数组。在用这个类初始化一个对象时，你不能确定该将这个数组的大小设置为多少，但知道这整个对象的大小是多少 byte，你就可以用到 flexible array。flexible array 必须是类中的最后一个成员，并且仅能有一个。在为对象分配内存时，flexible array 会自动填充，占用未被其他变量使用的内存。这样就可以确定自己的长度了。

例如我们有一个类 C：
```cpp
class C {
    int a; // 4 byte
    int array[1]; // unknown size
};
```
现在我们初始化一个 C 的对象，并为其分配了 24 Byte 的内存。`a` 占了 4 Byte 内存，那么 `array` 会尝试填充剩下的内存，大小变为 5。

实际上这就是 C++ 对象内存布局的一个简单的例子。因此 flexible array 为什么只能有一个且必须放在最后一个就很明显了，因为需要向后尝试填充。

此外，虽然成员在内存中的先后顺序和声明的顺序一致，但需要注意可能存在的内存对齐的问题。Header 中的数据大小都为 4 Byte，没有对齐问题。

到这里，这个大小为 1 的数组的作用就比较清楚了。利用 flexible array 的特性来自动填充 Page Data 4KB 减掉 Header 24B 后剩余的内存。剩下的这些内存用来存放 KV 对。

![](../../imgs/15-445-2-4.png)

Internal Page 中，KV 对的 K 是能够比较大小的索引，V 是 Page Id，用来指向下一层的节点。Project 中要求，第一个 Key 为空。主要是因为在 Internal Page 中，n 个 key 可以将数轴划分为 n+1 个区域，也就对应着 n+1 个 value。实际上你也可以把最后一个 key 当作是空的，只要后续的处理自洽就可以了。

![](../../imgs/15-445-2-5.png)

通过比较 key 的大小选中下一层的节点。实际上等号的位置也可以改变，总之，只要是合法的 B+ 树，即节点大小需要满足最大最小值的限制，各种实现细节都是自由的。

另外需要注意的是，Internal Page 中的 key 并不代表实际上的索引值，仅仅是作为一个向导，引导需要插入/删除/查询的 key 找到这个 key 真正所在的 Leaf Page。

**B_PLUS_TREE_LEAF_PAGE**
Leaf Page 和 Internal Page 的内存布局基本一样，只是 Leaf Page 多了一个成员变量 `next_page_id`，指向下一个 Leaf Page（用于 range scan）。因此 Leaf Page 的 Header 大小为 28 Byte。

Leaf Page 的 KV 对中，K 是实际的索引，V 是 Record Id。Record Id 用于识别表中的某一条数据，即一个 Tuple。这里也可以看出来 Bustub 所有的 B+ 树索引，无论是主键索引还是二级索引都是非聚簇索引。

> 这里简单介绍一下聚簇索引、非聚簇索引，主键索引、二级索引（非主键索引）的区别。
> 在聚簇索引里，Leaf Page 的 Value 为表中一条数据的某几个字段或所有字段，一定包含主键字段。而非聚簇索引 Leaf Page 的 Value 是 Record Id，即指向一条数据的指针。
> 在使用聚簇索引时，主键索引的 Leaf Page 包含所有字段，二级索引的 Leaf Page 包含主键和索引字段。当使用主键查询时，查询到 Leaf Page 即可获得整条数据。当使用二级索引查询时，若查询字段包含在索引内，可以直接得到结果，但如果查询字段不包含在索引内，则需使用得到的主键字段在主键索引中再次查询，以得到所有的字段，进而得到需要查询的字段，这就是回表的过程。
> 在使用非聚簇索引时，无论是使用主键查询还是二级索引查询，最终得到的结果都是 Record Id，需要使用 Record Id 去查询真正对应的整条记录。
> 聚簇索引的优点是，整条记录直接存放在 Leaf Page，无需二次查询，且缓存命中率高，在使用主键查询时性能比较好。缺点则是二级索引可能需要回表，且由于整条数据存放在 Leaf Page，更新索引的代价很高，页分裂、合并等情况开销比较大。
> 非聚簇索引的优点是，由于 Leaf Page 仅存放 Record Id，更新的代价较低，二级索引的性能和主键索引几乎相同。缺点是查询时均需使用 Record Id 进行二次查询。

Task1 的主要内容就是这些。实际上要实现的内容非常简单，重点是理解各个 Page 的作用和内存布局。

### Task2 B+Tree Data Structure (Insertion, Deletion, Point Search)
Task2 是单线程 B+ 树的重点。