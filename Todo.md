### Review

#### Commercial Instrument

- The microwave source and other commercial instrument (present or future) have standard interface. 

- Scripts can be easily made by python according to the command of SCPI.

#### Present Board

在操控比特脉冲的脚本与板子FPGA硬件之间需要一个类似 qubit sequencer的server。

> The qubit sequencer lives in between the data taking code and the GHz FPGA server.
> Its purpose is essentially organizational: it converts sequences defined in terms of qubit channels (e.g. XY, Z, readout) to sequences corresponding to hardware (e.g. DAC 14 A).



而Google现在已经停止更新pylabrad和相关的server，Martinis group的Github也被清空了。在完全不更换硬件情况下，可以接着用以前的版本。

如果要继续使用以前的板子，但更换部分仪器，比如fastbias更换为商用直流源。

那就需要重构qubit server。



Google之前版本的qubit server用java写的，后来改成scala，语言和java也很相似，但更方便。所以这种硬件相关面向对象的任务最好用类似java的语言，推荐在google较新的scala版上进行增改。





关于Labrad：

- labrad原始的逻辑，基本架构都是非常优秀的。可以自由添加server，server可用任意带有api的语言编写（google用过python，delphi，java，scala）
- Martinis group到google后软件的基本架构也还是基于labrad，google内部应该还帮忙完善过其它功能。而且即使是老版本的labrad在浙大也能够很好的进行20比特（实际肯定可以更多）的实验。



对labrad进行增改的主要任务是，根据硬件提供一个可编程设计量子比特实验脉冲的接口。

其他的像数据类型，参数储存等都可以继续沿用。而进一步的可视化GUI，和优化算法那些均可以直接在上层的脚本上完成，与底层硬件server无关。

