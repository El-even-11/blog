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

Project 3 的主要内容是为 Bustub 实现一系列 Query Execution 算子，以及小小体验一下 Query Optimization 的困难。Andy 在 Lecture 中说，Query Optimization 是数据库最难的部分，Transaction 是第二难的部分。总体来说，Project 3 的难度不算大，但和 Project 2 恰好是两个极端：Project 2 的难点在于从零实现 B+ 数，Project 3 的难点在于读代码，实现起来其实比较简单。

![](../../imgs/15-445-3-1.svg)