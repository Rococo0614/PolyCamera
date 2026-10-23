# 给 HAMMER 作者的问题草稿

不自动发布；由课题负责人确认后再通过 GitHub issue 或邮件发送。

## English draft

**Subject: Clarification on HAMMER polarization quadrant order and label IDs**

Hello, thank you for releasing the HAMMER dataset. We are studying polarization-guided enhancement of the commodity depth measurements in HAMMER and would like to confirm two data conventions before reporting physical polarization results.

1. Each `polarization/pol/*.png` is a 2x2 composite. What is the row-major quadrant order (top-left, top-right, bottom-left, bottom-right)? Is it `(0°, 45°, 90°, 135°)`, and do these angles follow the camera transmission-axis convention?
2. Which LUCID `PixelFormat` and on-camera processing were used? Were the four views demosaicked/ISP-processed before being tiled, and were exposure, gain, white balance, and gamma fixed?
3. The supplementary text mentions `0°, 90°, 180°, 270°`, while the camera normally exposes `0°, 45°, 90°, 135°`. Is the former a doubled-angle notation or a typo?
4. Is there a mapping from `_instance` label values to object/material categories? In `scene13`, visual overlays suggest label `140` groups reflective objects and label `160` groups transparent objects. Are these material IDs consistent across scenes?
5. Are the depth maps under the `polarization` view already warped and invalidated exactly as described in the supplement, and is `0` the only invalid-depth value?

We have checked the current LUCID pixel-format documentation and found that the `(q0+q2)` versus `(q1+q3)` orthogonal-pair hypothesis gives a substantially lower pair-sum residual on a sample, but we do not want to infer the absolute AoLP convention without confirmation.

Thank you for your help.

## 为什么必须问

- 问题 1--3 决定 AoLP 是否具有绝对物理意义；
- 问题 4 决定能否自动生成透明/反光分层指标；
- 问题 5 决定 coverage、silent-error 和配准误差的解释；
- 在未得到答复前，可以继续做全图深度和 DoLP 幅值审计，但不能宣称绝对法向方向或跨场景材质标签。
