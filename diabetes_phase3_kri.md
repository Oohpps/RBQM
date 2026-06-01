# 糖尿病 III 期临床研究项目关键风险指标建议

## 适用前提

本文档暂按常见项目场景设计：成人 2 型糖尿病、随机双盲、对照、III 期降糖药研究，主要终点通常为基线至预设时间点的 HbA1c 变化。

ICH E6(R3) 的核心不是指标数量，而是优先监控可能影响受试者保护和结果可靠性的关键质量因素（Critical-to-Quality Factors，CtQ），并对重要风险设置预设可接受范围。

## 建议的 15 项项目级 KRI

| 优先级 | 关键风险指标（KRI） | 推荐计算口径 | 监控层级 |
| --- | --- | --- | --- |
| 1 | HbA1c 主要终点缺失率 | 主要终点访视无有效 HbA1c 的受试者数 / 应评估受试者数 | 项目、中心 |
| 2 | 严重或临床重要低血糖发生率 | 严重低血糖、需他人协助事件、方案定义的重要低血糖事件数 / 暴露人年 | 项目、治疗组、中心 |
| 3 | 知情同意重大偏差率 | 未签署、版本错误、签署晚于研究操作的受试者数 / 入组受试者数 | 项目、中心 |
| 4 | 关键入排标准违背率 | 不符合关键入排标准但已随机化或给药的受试者数 / 随机受试者数 | 项目、中心 |
| 5 | SAE 报告超时率 | 超过规定时限报告的 SAE 数 / SAE 总数 | 项目、中心 |
| 6 | 提前停药与失访率 | 提前停药、退出研究或无法获得终点评估的受试者数 / 随机受试者数，并按原因拆分 | 项目、治疗组、中心 |
| 7 | 救援治疗使用率 | 启动救援治疗的受试者数 / 随机受试者数，并分析启动时间和原因 | 项目、治疗组、中心 |
| 8 | 试验药物依从性异常率 | 低于或高于方案规定依从区间的受试者数 / 已给药受试者数 | 项目、中心 |
| 9 | 禁用合并用药或降糖治疗调整偏差率 | 未按方案使用其他降糖药、胰岛素或激素等药物的受试者数 / 随机受试者数 | 项目、中心 |
| 10 | 关键安全检查缺失或处置延迟率 | 肾功能、肝功能、血糖等关键检查缺失，或异常结果未按时处置的受试者数 / 应评估受试者数 | 项目、中心 |
| 11 | HbA1c 评估超窗或方法偏差率 | HbA1c 超出访视窗口、实验室不合规或样本无效的受试者数 / 应评估受试者数 | 项目、中心、实验室 |
| 12 | 重大方案偏离率 | 影响受试者权益、安全性或主要终点可靠性的重大偏离数 / 随机受试者数 | 项目、中心 |
| 13 | 随机化与盲态偏差率 | 随机化错误、分层错误、非计划揭盲的受试者数 / 随机受试者数 | 项目、中心 |
| 14 | 中心异常模式评分 | 综合分析入组速度、筛败率、低血糖和 AE 报告率、HbA1c 变化、偏离率等指标相对于项目整体分布的异常程度 | 中心 |
| 15 | 关键数据完整性和及时性 | HbA1c、低血糖、用药、AE、实验室等关键数据缺失或延迟记录数 / 应记录数 | 项目、中心、供应商 |

## 建议优先设为项目级 QTL 的指标

15 项 KRI 不应全部设置为质量容忍限度（Quality Tolerance Limits，QTL）。建议将以下 6 项升级为项目层面的重点风险红线：

1. HbA1c 主要终点缺失率。
2. 严重低血糖事件率。
3. 知情同意重大偏差率。
4. 关键入排标准违背率。
5. SAE 报告超时率。
6. 提前停药、失访及终点不可评估率。

具体阈值应结合研究方案、统计假设、药物机制和既往研究设定。知情同意缺失等严重事件通常采用零容忍；其余指标可以同时使用预设绝对范围和中心相对异常阈值，不建议直接套用统一百分比。

## 按药物机制调整指标

| 药物类型或研究人群 | 建议增强或替换的风险指标 |
| --- | --- |
| 胰岛素或促泌剂 | 低血糖、剂量滴定偏差、血糖监测完整性 |
| SGLT2 抑制剂 | 酮症酸中毒、泌尿生殖系统感染、容量不足、肾功能变化 |
| GLP-1 类药物 | 胃肠道 AE、脱落率、胰腺炎相关信号、体重变化异常 |
| TZD 类药物 | 水肿、心衰相关事件、体重增加 |
| 肾功能受限人群 | eGFR 分层、肾功能恶化、剂量调整合规性 |
| 心血管高风险人群 | 主要不良心血管事件（MACE）、住院、死亡事件及独立判定积压 |

## 系统配置建议

建议为每个指标配置以下字段：

- CtQ 关联；
- 责任职能；
- 数据源；
- 计算频率；
- 最低分母；
- 阈值逻辑；
- 升级路径；
- 风险评估记录；
- 纠正和预防措施（CAPA）；
- 复核日期和关闭证据。

系统应支持零容忍阈值、绝对阈值、相对阈值和趋势阈值，并在中心样本量较小时提示观察，避免百分比造成误导。

## 参考资料

- [ICH E6(R3) Guideline for Good Clinical Practice，2025 年 10 月勘误版](https://database.ich.org/sites/default/files/ICH_E6%28R3%29_Step4_FinalGuideline_2025_0106_ErrorCorrections_2025_1024.pdf)
- [EMA Guideline on clinical investigation of medicinal products in the treatment or prevention of diabetes mellitus，Revision 2](https://www.ema.europa.eu/en/clinical-investigation-medicinal-products-treatment-or-prevention-diabetes-mellitus-scientific-guideline)
- [FDA Draft Guidance: Diabetes Mellitus: Efficacy Endpoints for Clinical Trials Investigating Antidiabetic Drugs and Biological Products](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/diabetes-mellitus-efficacy-endpoints-clinical-trials-investigating-antidiabetic-drugs-and-biological)
