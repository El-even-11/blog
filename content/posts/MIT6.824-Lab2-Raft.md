---

title: "MIT6.824 Lab2 Raft"
date: 2022-06-25T00:10:08+08:00
# weight: 1
# aliases: ["/first"]
tags: ["Raft", "Distributed System", "Consensus Algorithm"]
author: "Me"
# author: ["Me", "You"] # multiple authors
showToc: true
TocOpen: true
draft: false
hidemeta: false
comments: false
description: "The implementation of Raft consensus algorithm."
canonicalURL: "https://canonical.url/to/page"
disableHLJS: true # to disable highlightjs
disableShare: true
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
    image: "../../imgs/lab2A3.png" # image path/url
    alt: "" # alt text
    caption: "" # display caption under cover
    relative: false # when using page bundles set this to true
    hidden: false # only hide on current single page
editPost:
    URL: "https://github.com/el-even-11/blog/content"
    Text: "Suggest Changes" # edit text
    appendFilePath: true # to append file path to Edit link
---

趁着暑假有空，把鸽了很久的 MIT6.824 做一下。Lab1 是实现一个 Map-Reduce，因为和 Raft 主线关系不大（因为懒），就略过了。另外，这次尝试实现一个 part 就来记录相关的内容，以免在全部实现后忘记部分细节（以免之后太懒不想写）。因此，不同 part 的代码会变化，请以最终版本的代码为准（但保证每一 part 的代码可以正常通过**绝大部分**相应的测试）。同时，在写下某一 part 的记录时，我对 Raft 的整体把握也难免有所不足。

## Resources

- [Course's Page](https://pdos.csail.mit.edu/6.824/index.html) 课程主页
- [Students' Guide to Raft](https://thesquareplanet.com/blog/students-guide-to-raft/) 一篇引导博客
- [Debugging by Pretty Printing](https://blog.josejg.com/debugging-pretty/) debug 技巧，**强烈推荐阅读和运用**
- [Raft Q&A](https://thesquareplanet.com/blog/raft-qa/) 关于 Raft 的一些 Q&A
- [Raft Visualization](https://raft.github.io/) Raft 动画演示
- [In Search of an Understandable Consensus Algorithm](https://el-even-11.github.io/Blog/raft-extended.pdf) Raft 论文

## Lab2A Raft Leader Election

Lab2A 实现时间为6.22~6.24。

Lab2A 主要实现 Raft 的选主过程，包括选举出 Leader 和 Leader 通过心跳维持身份。



### Design

首先是选主过程的状态机模型：

![image-20220625172652039](../../imgs/lab2A2.png)

接下来是 Raft 论文中最为重要的 Figure 2:

![](../../imgs/lab2A1.png)

Figure 2 有许多关于日志复制等其他部分的内容，在这里暂时先不考虑（但当然还是推荐先整体熟悉 Raft 所有内容后再开始编码）。关于选举部分的内容已经全部在图中标出。一个一个看：

#### State

每个 Raft 节点需要维护的状态：

- `currentTerm` 此节点的任期。
- `votedFor` 在当前任期内，此节点将选票投给了谁。**一个任期内，节点只能将选票投给某一个节点**。因此当节点任期更新时要将 `votedfor` 置为 null。

#### AppendEntries RPC

在领导选举的过程中，`AppendEntries RPC` 用来实现 Leader 的心跳机制。节点的 `AppendEntries RPC` 会被 Leader 定期调用。

**Args**

- `term` Leader 的任期。
- `leaderId` Client 可能将请求发送至 Follower 节点，得知 `leaderId` 后 Follower 可将 Client 的请求重定位至 Leader 节点。因为 Raft 的请求信息必须先经过 Leader 节点，再由 Leader 节点流向其他节点进行同步，信息是单向流动的。**在选主过程中**，`leaderId` **暂时只有 debug 的作用**。

**Reply**

- `term` 此节点的任期。假如 Leader 发现 Follower 的任期高于自己，则会放弃 Leader 身份并更新自己的任期。
- `success` 此节点是否认同 Leader 发送的心跳。

**Receiver Implementation**

1. 当 Leader 任期小于当前节点任期时，返回 false。
2. 否则返回 true。

#### RequestVote RPC

`RequestVote RPC` 会被 Candidate 调用，以此获取选票。

**Args**

- `term` Candidate 的任期
- `candidateId`

**Reply**

- `term` 此节点的任期。假如 Candidate 发现 Follower 的任期高于自己，则会放弃 Candidate 身份并更新自己的任期。
- `voteGranted` 是否同意 Candidate 当选。

**Receiver Implementation**

1. 当 Candidate 任期小于当前节点任期时，返回 false。
2. 如果 `votedFor` 为 null（即当前任期内此节点还未投票）或者 `votedFor`为 `candidateId`（即当前任期内此节点已经向此 Candidate 投过票），则同意投票；否则拒绝投票。

#### Rules for Servers

**All Servers**

- 如果来自其他节点的 RPC 请求中，或发给其他节点的 RPC 的回复中，任期高于自身任期，则更新自身任期，并转变为 Follower。

**Followers**

- 响应来自 Candidate 和 Leader 的 RPC 请求。
- 如果在 election timeout 到期时，Follower 未收到来自当前 Leader 的 AppendEntries RPC，也没有收到来自 Candidate 的 RequestVote RPC，则转变为 Candidate。

**Candidates**

- 转变 Candidate时，开始一轮选举：
  - currentTerm++
  - 为自己投票（votedFor = me）
  - 重置 election timer
  - 向其他所有节点**并行**发送 RequestVote RPC
- 如果收到了大多数节点的选票（voteCnt > n/2），当选 Leader。
- 在选举过程中，如果收到了来自新 Leader 的 AppendEntries RPC，停止选举，转变为 Follower。
- 如果 election timer 超时时，还未当选 Leader，则放弃此轮选举，开启新一轮选举。

**Leaders**

- 刚上任时，向所有节点发送一轮心跳信息
- 此后，每隔一段固定时间，向所有节点发送一轮心跳信息，重置其他节点的 election timer，以维持自己 Leader 的身份。



至此，选主的流程已经比较清晰，接下来是具体的实现。



### Implementation

需要实现的结构体不再赘述，按照 Figure2 来就行。

首先实现两个RPC:

#### AppendEntries RPC

```go
func (rf *Raft) AppendEntries(args *AppendEntriesArgs, reply *AppendEntriesReply) {
	rf.mu.Lock()
	defer rf.mu.Unlock()
    
	if args.Term < rf.currentTerm {
        // Reply false if term < currentTerm
		reply.Success = false
		reply.Term = rf.currentTerm		
		return
	}

	if args.Term > rf.currentTerm {
        // If RPC request contains term T > currentTerm: 
        // set currentTerm = T, convert to follower
		rf.currentTerm = args.Term
		rf.votedFor = -1
		rf.state = FOLLOWER
	}

    // received AppendEntries RPC from current leader, reset election timer
	rf.electionTimer.Reset(randomElectionTimeout()) 

	reply.Success = true
	reply.Term = rf.currentTerm
}
```

#### RequestVote RPC

```go
func (rf *Raft) RequestVote(args *RequestVoteArgs, reply *RequestVoteReply) {
	rf.mu.Lock()
	defer rf.mu.Unlock()

	if args.Term < rf.currentTerm {
		// Reply false if term < currentTerm
		reply.VoteGranted = false
		reply.Term = rf.currentTerm
		return
	}

	if args.Term > rf.currentTerm {
		// If RPC request contains term T > currentTerm:
		// set currentTerm = T, convert to follower
		rf.currentTerm = args.Term
		rf.votedFor = -1
		rf.state = FOLLOWER
	}

	if rf.votedFor != -1 && rf.votedFor != args.CandidateId {
		// If votedFor is null or candidateId, grant vote; otherwise reject
		reply.VoteGranted = false
		reply.Term = rf.currentTerm
		return
	}

	// grant vote to candidate, reset election timer
	rf.electionTimer.Reset(randomElectionTimeout())
	rf.votedFor = args.CandidateId

	reply.VoteGranted = true
	reply.Term = rf.currentTerm
}
```



可以看到两个 RPC 的实现与 Figure 2 中的规则完全一致。依次实现即可。需要注意的是，处理 RPC 的整个过程中都需要持有锁。另外，在更新节点任期时，一定要同步将`votedFor` 置为 null。

实现完两个 RPC 后，再实现较为复杂的 election 和 heartbeat 过程。



#### Election

在节点的 election timer 过期后，开始选举。因此，节点需要有一个监控 electon timer 的 go routine，ticker。

```go
func (rf *Raft) ticker() {
	for !rf.killed() {
		select {
		case <-rf.electionTimer.C:
			rf.mu.Lock()
			if rf.state == LEADER {
				rf.mu.Unlock()
				break
			}
			rf.state = CANDIDATE
			rf.mu.Unlock()
			go rf.startElection()
		}
	}
}
```

选举过程的 go routine 为 startElection。为什么将选举过程也作为一个 go routine，而不是阻塞地调用函数？因为在规则中提到过，**如果 election timer 超时时，Candidate 还未当选 Leader，则放弃此轮选举，开启新一轮选举**。

接下来看实际负责选举过程的 go routine， startElection。

```go
func (rf *Raft) startElection() {
	rf.mu.Lock()
	rf.currentTerm++                                // Increment currentTerm
	rf.votedFor = rf.me                             // Vote for self
	rf.electionTimer.Reset(randomElectionTimeout()) // Reset election timer
	rf.mu.Unlock()

	args := RequestVoteArgs{CandidateId: rf.me}
	rf.mu.RLock()
	args.Term = rf.currentTerm
	rf.mu.RUnlock()

	voteCh := make(chan bool, len(rf.peers)-1)
	for i := range rf.peers { // Send RequestVote RPCs to all other servers
		if i == rf.me { // in PARALLEL
			continue
		}
		go func(i int) {
			reply := RequestVoteReply{}
			if ok := rf.sendRequestVote(i, &args, &reply); !ok {
				voteCh <- false
				return
			}
			rf.mu.Lock()
			if reply.Term > rf.currentTerm {
				// If RPC response contains term T > currentTerm:
				// set currentTerm = T, convert to follower
				rf.currentTerm = reply.Term
				rf.votedFor = -1
				rf.state = FOLLOWER
				rf.mu.Unlock()
				return
			}
			rf.mu.Unlock()
			voteCh <- reply.VoteGranted
		}(i)
	}

	voteCnt := 1
	voteGrantedCnt := 1
	for voteGranted := range voteCh {
		rf.mu.RLock()
		state := rf.state
		rf.mu.RUnlock()
		if state != CANDIDATE {
			break
		}
		if voteGranted {
			voteGrantedCnt++
		}
		if voteGrantedCnt > len(rf.peers)/2 {
			// gain over a half votes, switch to leader
			rf.mu.Lock()
			rf.state = LEADER
			rf.mu.Unlock()
			go rf.heartbeat()
			break
		}

		voteCnt++
		if voteCnt == len(rf.peers) {
			// election completed without getting enough votes, break
			break
		}
	}
}
```

使用 n-1 个协程向其他节点并行地发送 RequestVote 请求。协程获得 response 后，向 `voteCh` 发送结果，startElection 协程进行结果统计。统计过程中，若发现失去了 Candidate 身份，则停止统计。若获得票数过半，则成功当选 Leader，启动 heartbeat 协程。若所有成员已投票，且未当选 Leader，则退出统计。

要注意的是，需要确保所有不再使用的 go routine 能够正常退出，避免占据资源。

成功当选 Leader 后，开始发送心跳。

#### Heartbeat

```go
func (rf *Raft) heartbeat() {
	wakeChPool := make([]chan struct{}, len(rf.peers))
	doneChPool := make([]chan struct{}, len(rf.peers))
	// allocate each peer with a go routine to send AppendEntries RPCs
	for i := range rf.peers {
		if i == rf.me {
			continue
		}
		wakeChPool[i] = make(chan struct{})
		doneChPool[i] = make(chan struct{})
		go func(i int) { // replicator go routine
			for {
				select {
				case <-wakeChPool[i]:
					args := AppendEntriesArgs{LeaderId: rf.me}
					reply := AppendEntriesReply{}
					rf.mu.RLock()
					args.Term = rf.currentTerm
					rf.mu.RUnlock()

					go func() {
						if ok := rf.sendAppendEntries(i, &args, &reply); !ok {
							return
						}
						rf.mu.Lock()
						if reply.Term > rf.currentTerm {
							rf.currentTerm = reply.Term
							rf.votedFor = -1
							rf.state = FOLLOWER
							rf.mu.Unlock()
							return
						}
						rf.mu.Unlock()
					}()
				case <-doneChPool[i]:
					return
				}
			}
		}(i)
	}

	broadcast := func() {
		for i := range rf.peers {
			if i == rf.me {
				continue
			}
			go func(i int) {
				wakeChPool[i] <- struct{}{}
			}(i)
		}
	}
	broadcast()

	rf.heartbeatTimer = time.NewTimer(HEARTBEAT_INTERVAL)
	for {
		<-rf.heartbeatTimer.C
		if rf.killed() || !rf.isLeader() {
			break
		}
		rf.heartbeatTimer.Reset(HEARTBEAT_INTERVAL)
		broadcast()
	}

	// killed or no longer the leader, release go routines
	for i := range rf.peers {
		if i == rf.me {
			continue
		}
		go func(i int) {
			doneChPool[i] <- struct{}{}
		}(i)
	}
}
```

heartbeat 协程首先为每个节点分配一个 replicator 协程，每个 replicator 协程负责向一个特定的节点发送 AppendEntries RPC。

这些协程由 `wakeChPool[i]` 唤醒。实际上也可以用 `sync.Cond` 条件变量实现，但我不太会用，所以简单地用一组 channel 模拟。

初始化这些协程后，heartbeat 协程首先进行一个初始的 broadcast，对应 Leader 刚当选时发出的一轮心跳。broadcast 即通过 `wakeChPool` 唤醒所有 replicator 协程，向所有节点发出一次心跳。

此后，heartbeat 协程初始化一个 heartbeatTimer，并且在每次 heartbeatTimer 到期时，进行一次 broadcast，通知所有 replicator 协程发送一次心跳。这里需要注意的是，如果节点已经被 kill 或者不再是 Leader，需要中断对 heartbeatTimer 的监听，并且释放所有 replicator 协程。

至此，选主过程和心跳成功实现。



### Devil in the details

Lab2A 难度不算大，然而我还是被一个细节卡住了挺久。

在 6.824 Raft 实验中，已经给我们提供了 RPC 调用的方法，即

```go
rf.peers[server].Call("Raft.RPCName", args, reply)
```

其注释提到，

> Call() is guaranteed to return (perhaps after a delay) *except* if the handler function on the server side does not return.  Thus there is no need to implement your own timeouts around Call().

Call() 是确保一定会返回的，除非在被调用的RPC中阻塞，否则即使模拟的网络中断，Call() 也会正常返回 false。因此不需要再为 Call() 设置一个 Timeout 限制。

然而，经过测试，Call() 的确会确保返回，但返回的时间可能会非常长（3到4秒，具体数值要阅读 labrpc 源码，我还没有仔细阅读）。因此，在 replicator 协程中，每次发送心跳，我们还要再启动一个协程，将 sendAppendEntries 放在此协程中运行，避免哪怕只有几秒钟的阻塞。因为在这几秒中，Leader 可能又发送了新的 heartbeat，或者 Leader 不再是 Leader。

```go
go func(i int) { // replicator go routine
	for {
		select {
		case <-wakeChPool[i]:
			...
			go func() { // launch a new go routine to run sending RPC
				if ok := rf.sendAppendEntries(i, &args, &reply); !ok {
					return
				}
			}()
		case <-doneChPool[i]:
			return
		}
		...
	}
}(i)
```



### Summary

个人感觉 Lab2A 难度最大的地方在于合理控制各个 go routine 的生命周期。锁倒是暂时没碰到什么问题，直接一股脑地把可能存在 data race 的地方全部锁上并及时释放就好。整个选主过程的 go routine 生命周期如下：

![](../../imgs/lab2A3.png)

Lab2A Leader Election 完成。



## Lab2B Raft Log Replication

Lab2B 开始于 6.28。结束于7.7。

和 Raft 最核心的部分缠斗了一个多星期，终于敢说完成了一个较为稳定的版本，千次测试无一 fail。这段时间摸摸鱼，陪陪女朋友，玩玩游戏（和朋友们一起玩一款叫 Raft 的海上生存游戏，挺巧），无聊的时候再看看 fail 掉的 log，暑假嘛，开心最重要。

关于 Lab2B 感触最深的就是 [Students' Guide to Raft](https://thesquareplanet.com/blog/students-guide-to-raft/) 里的这两段话：

> At first, you might be tempted to treat Figure 2 as sort of an informal guide; you read it once, and then start coding up an implementation that follows roughly what it says to do. Doing this, you will quickly get up and running with a mostly working Raft implementation. And then the problems start.

> Inevitably, the first iteration of your Raft implementation will be buggy. So will the second. And third. And fourth.

完成第一版可以单次 pass 的代码大概用了5个小时左右，接下来信心满满地进行千次测试。然而随后的大部分时间，我基本都在试图从各种诡异的 log 找出出现概率极低的难以复现的 Bug。

![](../../imgs/lab2B1.png)



### Design

首先还是 Figure 2：

![](../../imgs/lab2B2.png)

Lab2B 中需要完成 Figure 2 中余下的所有内容。顺带一提的是，Figure 2 与其说是一个 Raft 行为的汇总，更像是一个 coding 的 instruction。Figure 2 中很多地方直接给出了代码的具体行为，而不是给出比较抽象和模糊的规则。这样的好处是，coding 更加简单了，严格遵守 Figure 2 即可；但也有一定的坏处，可能实现完所有部分后，学生（特指我）还是对 Raft 的行为，设计和一致性证明等等比较模糊，仅是机械地遵循了 Figure 2 中给出的规则。下面还是一个一个来介绍：

#### State

- `log[]` 即日志，每条 Entry 包含一条待施加至状态机的命令。Entry 也要记录其被发送至 Leader 时，Leader 当时的任期。Lab2B 中，在内存存储日志即可，不用担心 server 会 down 掉，测试中仅会模拟网络挂掉的情景。
- `commitIndex` 已知的最高的**已提交**的 Entry 的 index。**被提交**的定义为，当 Leader 成功在大部分 server 上复制了一条 Entry，那么这条 Entry 就是一条**已提交**的 Entry。
- `lastApplied` 最高的**已应用**的 Entry 的 index。已提交和已应用是不同的概念，已应用指这条 Entry 已经被运用到状态机上。已提交先于已应用。同时需要注意的是，Raft 保证了已提交的 Entry 一定会被应用（通过对选举过程增加一些限制，下面会提到）。

commitIndex 和 lastApplied 分别维护 log 已提交和已应用的状态，当节点发现 commitIndex > lastApplied 时，代表着 commitIndex 和 lastApplied 间的 entries 处于已提交，未应用的状态。因此应将其间的 entries **按序**应用至状态机。

对于 Follower，commitIndex 通过 Leader AppendEntries RPC 的参数 leaderCommit 更新。对于 Leader，commitIndex 通过其维护的 matchIndex 数组更新。

- `nextIndex[]`  由 Leader 维护，`nextIndex[i]` 代表需要同步给 `peer[i]` 的下一个 entry 的 index。在 Leader 当选后，重新初始化为 Leader 的 last log index + 1。
- `matchIndex[]` 由 Leader 维护，`matchIndex[i]` 代表 Leader 已知的已在 `peer[i]` 上成功复制的最高 entry index。在 Leader 当选后，重新初始化为 0。

不能简单地认为 matchIndex = nextIndex - 1。

nextIndex 是对追加位置的一种猜测，是乐观的估计。因此，当 Leader 上任时，会将 nextIndex 全部初始化为 last log index + 1，即乐观地估计所有 Follower 的 log 已经与自身相同。AppendEntries PRC 中，Leader 会根据 nextIndex 来决定向 Follower 发送哪些 entry。当返回失败时，则会将 nextIndex 减一，猜测仅有一条 entry 不一致，再次乐观地尝试。实际上，使用 nextIndex 是为了提升性能，仅向 Follower 发送不一致的 entry，减小 RPC 传输量。

matchIndex 则是对同步情况的保守确认，为了保证安全性。matchIndex 及此前的 entry 一定都成功地同步。matchIndex 的作用是帮助 Leader 更新自身的 commitIndex。当 Leader 发现一个 N 值，N 大于过半数的 matchIndex，则可将其 commitIndex 更新为 N（需要注意任期号的问题，后文会提到）。matchIndex 在 Leader 上任时被初始化为 0。

nextIndex 是最乐观的估计，被初始化为最大可能值；matchIndex 是最悲观的估计，被初始化为最小可能值。在一次次心跳中，nextIndex 不断减小，matchIndex 不断增大，直至 matchIndex = nextIndex - 1，则代表该 Follower 已经与 Leader 成功同步。

#### AppendEntries RPC

**Args**

- `prevLogIndex`  添加 Entries 的前一条 Entry 的 index。
- `prevLogTerm` prevLogIndex 对应 entry 的 term。
- `entries[]` 需要同步的 entries。若为空，则代表是一次 heartbeat。需要注意的是，不需要特别判断是否为 heartbeat，即使是 heartbeat，也需要进行一系列的检查。因此本文也不再区分心跳和 AppendEntries RPC。
- `leaderCommit` Leader 的 commitIndex，帮助 Follower 更新自身的 commitIndex。

**Receiver Implementation**

1. 若 Follower 在 prevLogIndex 位置的 entry 的 term 与 prevLogTerm 不同（或者 prevLogIndex 的位置没有 entry），返回 false。
2. 如果 Follower 的某一个 entry 与需要同步的 entries 中的一个 entry 冲突，则需要删除冲突 entry 及其之后的所有 entry。需要特别注意的是，**假如没有冲突，不能删除任何 entry**。因为存在 Follower 的 log 更 up-to-date 的可能。
3. 添加 Log 中不存在的新 entry。
4. 如果 leaderCommit > commitIndex，令 commitIndex = min(leaderCommit, index of last new entry)。此即 Follower 更新 commitIndex 的方式。

![](../../imgs/lab2B3.png)

#### RequestVote RPC

**Args**

- `lastLogIndex` Candidate 最后一个 entry 的 index，是投票的额外判据。
- `lastLogTerm` 上述 entry 的 term。

**Receiver Implementation**

- 只有 Candidate 的 log 至少与 Receiver 的 log 一样**新（up-to-date）**时，才同意投票。Raft 通过两个日志的最后一个 entry 来判断哪个日志更 **up-to-date**。假如两个 entry 的 term 不同，term 更大的更新。term 相同时，index 更大的更新。

  > Raft determines which of two logs is more up-to-date by comparing the index and term of the last entries in the logs. If the logs have last entries with different terms, then the log with the later term is more up-to-date. If the logs end with the same term, then whichever log is longer is more up-to-date.

这里投票的额外限制是为了保证已经被 commit 的 entry 一定不会被覆盖。仅有当 Candidate 的 log 包含所有已提交的 entry，才有可能当选为 Leader。

#### Rules for Servers 

**All Severs**

- 如果 commitIndex > lastApplied，lastApplied++，将 log[lastApplied] 应用到状态机。即前文提到的 entry 从已提交状态到已应用状态的过程。

**Leaders**

- 如果收到了来自 client 的 command，将 command 以 entry 的形式添加到日志。在 lab2B 中，client 通过 Start() 函数传入 command。

- 如果 last log index >= nextIndex[i]，向 peer[i] 发送 AppendEntries RPC，RPC 中包含从 nextIndex[i] 开始的日志。
  - 如果返回值为 true，更新 nextIndex[i] 和 matchIndex[i]。
  - 如果因为 entry 冲突，RPC 返回值为 false，则将 nextIndex[i] 减1并重试。这里的重试不一定代表需要立即重试，实际上可以仅将 nextIndex[i] 减1，下次心跳时则是以新值重试。

- 如果存在 index 值 N 满足：

  - N > commitIndex
  - 过半数 matchIndex[i] >= N
  - log[N].term == currentTerm

  则令 commitIndex = N。

  这里则是 Leader 更新 commitIndex 的方式。前两个要求都比较好理解，第三个要求是 Raft 的一个特性，即 Leader 仅会直接提交其任期内的 entry。存在这样一种情况，Leader 上任时，其最新的一些条目可能被认为处于未被提交的状态（但这些条目实际已经成功同步到了大部分节点上）。Leader 在上任时并不会检查这些 entry 是不是实际上已经可以被提交，而是通过提交此后的 entry 来间接地提交这些 entry。这种做法能够 work 的基础是 Log Matching Property：

  > **Log Matching**: if two logs contain an entry with the same index and term, then the logs are identical in all entries up through the given index.

  原文描述如下：

  > To eliminate problems like the one in Figure 8, **Raft never commits log entries from previous terms by counting replicas**. Only log entries from the leader’s current term are committed by counting replicas; once an entry from the current term has been committed in this way, then all prior entries are committed indirectly because of the Log Matching Property. There are some situations where a leader could safely conclude that an older log entry is committed (for example, if that entry is stored on every server), but Raft takes a more conservative approach for simplicity.

  ![](../../imgs/lab2B4.png)
  
  这样简化了 Leader 当选的初始化工作，也成功避免了简单地通过 counting replicas 提交时，可能出现的已提交 entry 被覆盖的问题。

到这里 Figure 2 基本介绍完毕。也大致解释了 Figure 2 中各种规则的缘由。Raft 论文中还有更多 Raft 的设计理念、Properties、安全性证明等内容，这里就不再赘述了。

