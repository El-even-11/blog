---
title: "CMU15-445 Project3 Query Execution"
date: 2022-11-26T22:57:31+08:00
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
description: "Building the Query Execution Engine for Bustub."
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

来记录一下 Bustub Query Execution 的实现过程。

在阅读本文前，墙裂推荐阅读 Project 3 开发者迟先生的这篇文章：
[BusTub 养成记：从课程项目到 SQL 数据库](https://zhuanlan.zhihu.com/p/570917775)
可以更清晰地了解到 Bustub SQL 层的设计过程。

## Resources

- [https://15445.courses.cs.cmu.edu/fall2022](https://15445.courses.cs.cmu.edu/fall2022) 课程官网
- [https://github.com/cmu-db/bustub](https://github.com/cmu-db/bustub) Bustub Github Repo
- [https://www.gradescope.com/](https://www.gradescope.com/) 自动测评网站 GradeScope，course entry code: PXWVR5
- [https://discord.gg/YF7dMCg](https://discord.gg/YF7dMCg) Discord 论坛，课程交流用
- bilibili 有搬运的课程视频，自寻。
- [https://15445.courses.cs.cmu.edu/fall2022/bustub/](https://15445.courses.cs.cmu.edu/fall2022/bustub/) 在你的浏览器上运行 Bustub！

**请不要将实现代码公开，尊重 Andy 和 TAs 的劳动成果！**

## Overview

Andy 在 Lecture 中说，Query Optimization 是数据库最难的部分，Transaction 是第二难的部分。总体来说，Project 3 的难度不算大，但和 Project 2 的难点恰好相反：Project 2 的难点在于从零实现 B+ 树，一切都得靠自己。Project 3 的难点在于读代码，理解查询引擎的原理，具体实现起来其实比较简单。

![](../../imgs/15-445-3-1.svg)

这是课程官网的一张图，清晰地介绍了 Bustub 的整体架构。在 Project 3 中，我们需要实现一系列 Executors，以及为 Optimizer 添加新功能。

- Task1：Access Method Executors. 包含 SeqScan、Insert、Delete、IndexScan 四个算子。
- Task2：Aggregation and Join Executors. 包含 Aggregation、NestedLoopJoin、NestedIndexJoin 三个算子。
- Task3：Sort + Limit Executors and Top-N Optimization. 包含 Sort、Limit、TopN 三个算子，以及实现将 Sort + Limit 优化为 TopN 算子。
- Leaderboard Task：为 Optimizer 实现新的优化规则，包括 Hash Join、Join Reordering、Filter Push Down、Column Pruning 等等，让三条诡异的 sql 语句执行地越快越好。
## Talking Casually

在正式开始记录 Project 3 的具体实现之前，我想随便聊聊 Bustub 整体的结构与运行流程。在迷迷糊糊地通过 Project 3 的所有 tests 后，我意识到这其实是了解数据库到底是如何执行 sql 语句的最佳时机。Project 1&2 都比较局部，而在这里，一个能真正执行 sql 语句的数据库已经构建起来了。先暂时抛开 transaction，来看看一条 sql 语句在 Bustub 中的旅行。

![](../../imgs/15-445-3-2.png)

### Parser

一条 sql 语句，首先经过  Parser 生成一棵抽象语法树 AST。具体如何生成，请参考编译原理。Parser 不是数据库的核心部分，也不是性能瓶颈，因此除非热爱编译原理，或者想通过实现一个 sql Parser 对编译原理进行实践，否则一般都会采用第三方库。Bustub 中采用了 libpg_query 库将 sql 语句 parse 为 AST。

### Binder

在得到 AST 后，还需要将这些词语绑定到数据库实体上，这就是 Binder 的工作。例如有这样一条 sql：

```sql
SELECT colA FROM table1;
```

其中 `SELECT` 和 `FROM` 是关键字，`colA` 和 `table1` 是标识符。Binder 遍历 AST，将这些词语绑定到相应的实体上。实体是 Bustub 可以理解的各种 c++ 类。绑定完成后，得到的结果是一棵 Bustub 可以直接理解的树。把它叫做 Bustub AST。

### Planner

得到 Bustub AST 后，Planner 遍历这棵树，生成初步的查询计划。查询计划也是一棵树的形式。例如这条 sql：

```sql
SELECT t1.y, t2.x FROM t1 INNER JOIN t2 ON t1.x = t2.y;
```

对应的原始的查询计划是

![](../../imgs/15-445-3-3.png)

查询计划规定了数据的流向。数据从树叶流向树根，自底向上地流动，在根节点输出结果。

### Optimizer

由 Planner 得到初步的查询计划后，再将查询计划交给 Optimizer 进行修改优化，生成优化过后的最终查询计划。Optimizer 主要有两种实现方式：

1. Rule-based. Optimizer 遍历初步查询计划，根据已经定义好的一系列规则，对 PlanNode 进行一系列的修改、聚合等操作。例如我们在 Task 3 中将要实现的，将 Limit + Sort 合并为 TopN。这种 Optimizer 不需要知道数据的具体内容，仅是根据预先定义好的规则修改 Plan Node。
2. Cost-based. 这种 Optimizer 首先需要读取数据，利用统计学模型来预测不同形式但结果等价的查询计划的 cost。最终选出 cost 最小的查询计划作为最终的查询计划。

Bustub 的 Optimizer 采用第一种实现方式。MIT6.830 的 SimpleDB 则是采用第二种方式，有兴趣也可以看看。

另外值得一提的是，一般来说，Planner 生成的是 Logical Plan Node，代表抽象的 Plan。Optimizer 则生成 Physical Plan Node，代表具体执行的 Plan。一个比较典型的例子是 Join。在 Planner 生成的查询计划中，Join 就是 Join。在 Optimizer 生成的查询计划中，Join 会被优化成具体的 HashJoin 或 NestedIndexJoin 等等。在 Bustub 中，并不区分 Logical Plan Node 和 Physical Plan Node。Planner 会直接生成 Physical Plan Node。

### Executor

在拿到 Optimizer 生成的具体的查询计划后，就可以生成真正执行查询计划的一系列算子了。算子也是我们在 Project 3 中需要实现的主要内容。生成算子的步骤很简单，遍历查询计划树，将树上的 PlanNode 替换成对应的 Executor。算子的执行模型也大致分为三种：

1. Iterator Model，或者说火山模型。每个算子都有 `Init()` 和 `Next()` 两个方法。`Init()` 对算子进行初始化工作。`Next()` 则是向下层算子请求下一条数据。当 `Next()` 返回 false 时，则代表下层算子已经没有剩余数据，迭代结束。可以看到，火山模型一次调用请求一条数据，占用内存较小，但函数调用开销大，特别是虚函数调用造成 cache miss 等问题。
2. Materialization Model. 所有算子立即计算出所有结果并返回。和 Iterator Model 相反。这种模型的弊端显而易见，当数据量较大时，内存占用很高。但减少了函数调用的开销。比较适合查询数据量较小的 OLTP workloads。
3. Vectorization Model. 对上面两种模型的中和，一次调用返回一批数据。利于 SIMD 加速。目前比较先进的 OLAP 数据库都采用这种模型。

Bustub 采用的是 Iterator Model。

此外，算子的执行方向也有两种：

1. Top-to-Bottom. 从根节点算子开始，不断地 pull 下层算子的数据。
2. Bottom-to-Top. 从叶子节点算子开始，向上层算子 push 自己的数据。

Bustub 采用 Top-to-Bottom。

在根节点算子处，就得到了我们想要查询的数据，一条 sql 语句完成了它的使命。

另外，我们在 Project 1 中实现的 Buffer Pool 和在 Project 2 中实现的 B+Tree Index 在哪里？实际上就在一系列算子下。例如 SeqScan 算子，需要遍历 table，首先通过数据库的 catalog 找到对应的 table，一个 table 由许多 page 组成，在访问 page 时，就用到了 Buffer Pool。在 Optimizer 中，假如发现 Sort 算子在对 indexed attribute 排序，会将 Sort 算子优化为 IndexScan 算子，这样就用到了 B+Tree Index。

Bustub Query Execution 的大致结构就是这样，还有很多设计上的细节没有提到，比如 Tuple、Value、AbstractExpression 等等。接下来在具体实现中边看边聊。

## Task 1 Access Method Executors

Task 1 包含 3 个算子，SeqScan、Insert 和 Delete。

### SeqScan

读取给定 table 中的所有 tuple，仅会出现在查询计划的叶子节点处。直接使用已经提供的 `TableIterator`。实现起来挺简单的。此外主要想聊聊 Bustub 中 table 的结构。

![](../../imgs/15-445-3-4.png)

首先，Bustub 有一个 Catalog。Catalog 提供了一系列 API，例如 `CreateTable()`、`GetTable()` 等等。Catalog 维护了几张 hashmap，保存了 table id 和 table name 到 table info 的映射关系。table id 由 Catalog 在新建 table 时自动分配，table name 则由用户指定。

这里的 table info 包含了一张 table 的 metadata，有 schema、name、id 和指向 table heap 的指针。系统的其他部分想要访问一张 table 时，先使用 name 或 id 从 Catalog 得到 table info，再访问 table info 中的 table heap。

table heap 是管理 table 数据的结构，包含 `InsertTuple()`、`MarkDelete()` 一系列 table 相关操作。table heap 本身并不直接存储 tuple 数据，tuple 数据都存放在 table page 中。table heap 可能由多个 table page 组成，仅保存其第一个 table page 的 page id。需要访问某个 table page 时，通过 page id 经由 buffer pool 访问。

table page 是实际存储 table 数据的结构，父类是 page。相较于 page，table page 多了一些新的方法。table page 在 data 的开头存放了 next page id、prev page id 等信息，将多个 table page 连成一个双向链表，便于整张 table 的遍历操作。当需要新增 tuple 时，table heap 会找到当前属于自己的最后一张 table page，尝试插入，若最后一张 table page 已满，则新建一张 table page 插入 tuple。table page 低地址存放 header，tuple 从高地址也就是 table page 尾部开始插入。

tuple 对应数据表中的一行数据。每个 tuple 都由 RID 唯一标识。RID 由 page id + slot num 构成。tuple 由 value 组成，value 的个数和类型由 table info 中的 schema 指定。

value 则是某个字段具体的值，value 本身还保存了类型信息。

将这些内容理清楚后，SeqScan 就很好实现了。需要注意的是，executor 本身并不保存查询计划的信息，应该通过 executor 的成员 plan 来得知该如何进行本次计算，例如 SeqScanExecutor 需要向 SeqScanPlanNode 询问自己该扫描哪张表。

所有要用到的系统资源，例如 Catalog，Buffer Pool 等，都由 `ExecutorContext` 提供。

### Insert & Delete

Insert 和 Delete 这两个算子实现起来基本一样，也比较特殊。数据库最主要的操作就是增查删改。Bustub 暂时没有改的操作（实际删后再增也差不多），重点也在查上。Insert 和 Delete 一定是查询计划的根节点，且仅需返回一个代表修改行数的 tuple。