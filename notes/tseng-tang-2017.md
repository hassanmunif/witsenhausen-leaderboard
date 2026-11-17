# Re-examining the 0.166897 of Tseng and Tang (CDC 2017)

*Checked on 2026-11-17 with [`scripts/reexamine/tseng_tang_tails.py`](../scripts/reexamine/tseng_tang_tails.py) and [`scripts/reexamine/tseng_tang_grid.py`](../scripts/reexamine/tseng_tang_grid.py). Each runs from the repository root in under a minute.*

## Summary

Tseng and Tang [1] report a cost of 0.166897 at the benchmark $k = 0.2$, $\sigma = 5$, about $2.6 \times 10^{-5}$ below the next best printed cost. That number is not the exact cost of their controller. Their numerics leave out the noise beyond $\pm 5$ standard deviations, and for a step controller that part of the cost is about $2.5 \times 10^{-5}$. Scored the same way, the verified reference controllers on this site reproduce the paper's Table II to the printed precision for $k = 0.2$ to $0.5$. Adding back what the cutoff leaves out puts their controller at about $0.166922$: level with the verified record, $0.166922312$, and with Mehmetoglu et al., $0.16692291$. The leaderboard keeps the row as *Claimed*, with its printed cost, and marks it *disputed*.

## What the paper and its code do

The paper says that $x_1$ and $u_1$ are supported on $[-25, 25]$ and $[-30, 30]$, and that each support is partitioned evenly by 16,000 points. It does not say how the noise is integrated. The code behind the paper is not public, but its successor is: the UCP-Solver of Tseng [2, 3], which reports the same 0.166897 for the benchmark. Its cost function, `Witsenhausen::get_J_value` in [`witsenhausen.cpp`](https://github.com/shih-hao-tseng/UCP-Solver/blob/ca1e1fc22abe32805d1d06f5cd1e2d2d8c2f3bff/single_threaded/sources/witsenhausen.cpp#L20-L44), samples the noise on the same grid as $x_0$, scaled by $\sigma_w / \sigma_x$:

```cpp
w = _sample_coord[sample_w] * _sigma_w_to_x_ratio;
```

So $x_0$ only takes values in $[-25, 25]$ and $w$ only in $[-5, 5]$. The probabilities are not renormalised; the program prints their totals, which are both $0.99999943$.

## Why five standard deviations is not enough here

A good controller sends $x_0$ to levels about 6.6 apart near the centre. The second controller picks the wrong level when the noise is larger than about half that spacing. Noise beyond $\pm 5$ has probability $5.7 \times 10^{-7}$, but each such event costs a squared error of about one spacing squared, roughly 45. Leaving these events out lowers the cost by about $2.5 \times 10^{-5}$, the whole gap between 0.166897 and the other results. A five-sigma cutoff is harmless for a smooth integrand, but here the region it drops is exactly where the costly errors happen.

## Check 1: the exact cost minus what the cutoff leaves out

`tseng_tang_tails.py` scores the verified reference controllers with the reference evaluator and subtracts the three pieces that the cutoff leaves out: the first- and second-stage cost for $|x_0| > 5\sigma$, and the second-stage cost for $|x_0| \le 5\sigma$, $|w| > 5$. The last piece is almost all of it. Where Table II is essentially linear ($k \ge 0.75$), the best linear controller is used.

| $k$ | controller | exact cost | left out | with the cutoff | Table II | Table II minus cutoff |
|---|---|---|---|---|---|---|
| 0.1 | verified reference | 0.0523196 | 3.19e-05 | 0.0522878 | 0.052292 | +4.2e-06 |
| 0.2 | verified reference | 0.1669223 | 2.51e-05 | 0.1668973 | 0.166897 | −2.6e-07 |
| 0.3 | verified reference | 0.3148453 | 2.10e-05 | 0.3148244 | 0.314824 | −3.5e-07 |
| 0.4 | verified reference | 0.4776710 | 1.85e-05 | 0.4776524 | 0.477652 | −4.2e-07 |
| 0.5 | verified reference | 0.6409912 | 1.68e-05 | 0.6409744 | 0.640974 | −3.7e-07 |
| 0.75 | best linear | 0.9614405 | 1.54e-05 | 0.9614251 | 0.961424 | −1.1e-06 |
| 1 | best linear | 0.9614835 | 1.54e-05 | 0.9614681 | 0.961467 | −1.1e-06 |
| 8 | best linear | 0.9615376 | 1.54e-05 | 0.9615222 | 0.961522 | −2.1e-07 |

For $k = 0.2$ to $0.5$ the verified controllers, scored with the cutoff, give the paper's numbers to within the rounding of the sixth decimal. At $k = 0.1$ the verified controller is better than the paper's even with the cutoff.

The linear rows are a check inside the paper itself. For every $k$ from 0.75 to 8, Table II is about $1.6 \times 10^{-5}$ below the exact cost of the best linear controller (at $k = 8$: 0.961522 against 0.9615376). A real improvement would not stay constant while $k^2$ grows a hundredfold, and the cutoff reproduces it.

## Check 2: their cost formula on their grid

`tseng_tang_grid.py` re-implements `get_J_value` in numpy on the grid stated in the paper: 16,000 points of $[-25, 25]$ for $x_0$, the noise on the same points divided by 5, and the second controller on 16,000 points of $[-30, 30]$, set to the conditional mean of $x_1$ given $y$ in this discrete model. Probabilities are computed as in the solver, and nothing is renormalised.

| $k$ | exact cost | on their grid | Table II |
|---|---|---|---|
| 0.1 | 0.0523196 | 0.0522878 | 0.052292 |
| 0.2 | 0.1669223 | 0.1668973 | 0.166897 |
| 0.3 | 0.3148453 | 0.3148244 | 0.314824 |
| 0.4 | 0.4776710 | 0.4776524 | 0.477652 |
| 0.5 | 0.6409912 | 0.6409743 | 0.640974 |

The two checks agree to about $10^{-7}$.

## What this shows and what it does not

The controller of Tseng and Tang is not published, so its exact cost cannot be computed here. The checks show that its cost with the cutoff equals that of the verified reference controller to within the printed precision, and that the cutoff leaves out about $2.5 \times 10^{-5}$ for a controller of this shape. Its exact cost is therefore about 0.166922, within about $10^{-6}$ of the verified record, so it is not a better controller. The search algorithm itself is not in question, only the way the reported cost was computed.

## References

1. S.-H. Tseng and A. Tang, "A local search algorithm for the Witsenhausen's counterexample," *Proc. 56th IEEE Conference on Decision and Control*, 2017, pp. 5014–5019. [doi:10.1109/CDC.2017.8264401](https://doi.org/10.1109/CDC.2017.8264401), [PDF](https://people.ece.cornell.edu/atang/pub/17/CDC17.pdf).
2. S.-H. Tseng, "A generic solver for unconstrained control problems with integral functional objectives," *Proc. American Control Conference*, 2020. [doi:10.23919/ACC45564.2020.9147560](https://doi.org/10.23919/ACC45564.2020.9147560), [arXiv:1908.04489](https://arxiv.org/abs/1908.04489).
3. UCP-Solver, <https://github.com/shih-hao-tseng/UCP-Solver>, commit `ca1e1fc` (2020-03-12).
