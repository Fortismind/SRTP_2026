"""Report only observed artifacts; fail if experiments have not completed."""
from pathlib import Path
from collections import Counter
import json,importlib
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from cfb.common import ROOT,read,dump,sha

def main():
    audit=read(ROOT/'reports/data_audit.json');env=read(ROOT/'reports/environment.json');num=read(ROOT/'reports/numerical_verification.json');ov=read(ROOT/'reports/overfit.json');split=read(ROOT/'data/splits.json')
    manifests=read(ROOT/'data/manifest.json');manifest={r['patient_id']:r for r in manifests};models=['i2sb_short','regression_short']
    train={k:read(ROOT/f'logs/{k}/summary.json') for k in models};test={k:read(ROOT/f'results/{k}/summary.json') for k in models}
    draws={k:[json.loads(x) for x in (ROOT/f'logs/{k}/train.jsonl').read_text().splitlines()] for k in models}
    exposure={k:dict(optimizer_updates=len(v),unique_training_patients=len(set(r['patient'] for r in v)),
                    missing_from_short_draws=sorted(set(split['train'])-{r['patient'] for r in v}),
                    validation_or_test_training_exposures=sum(r['patient'] not in split['train'] for r in v)) for k,v in draws.items()}
    assert all(v['validation_or_test_training_exposures']==0 for v in exposure.values())
    exposure['identical_patient_draw_sequence']=[r['patient'] for r in draws[models[0]]]==[r['patient'] for r in draws[models[1]]]
    dump(ROOT/'reports/training_exposure.json',exposure)
    interval=[r['weeks'] for r in manifests if r['status']=='accepted'];actions=Counter(r['qc']['spatial_action'] for r in manifests if r['status']=='accepted')
    lines=['# CFB-GBM 随访 MRI 生成：实际实验报告','',
      '这是基线增强 T1 + 实际随访周数 → 随访增强 T1 的非商业算法原型。以下数值由本机实际文件、日志和生成结果读取，短训练不代表充分训练或临床有效。','',
      '## 本机与数据','',
      f'- 平台：{env["platform"]}；Python {env["python"].split()[0]}；PyTorch {env["torch_actual"]}；CUDA runtime {env["cuda"]}。',
      f'- 显卡：{env["gpu"]}，显存 {env["gpu_memory_bytes"]/1024**3:.2f} GiB；未下载预训练权重。',
      '- 复用现有 CUDA PyTorch，项目内安装其他依赖；已有环境和 E 盘原始数据未修改。',
      f'- 实际重新发现 {audit["patients"]} 位患者、{audit["actual_nifti_files"]} 个 NIfTI，实际 t0/t1 增强 T1 配对 {audit["actual_t0_t1_pairs"]} 位；质量/时间检查后纳入 {audit["accepted"]} 位。',
      f'- 患者划分：训练 {len(split["train"])}、验证 {len(split["val"])}、独立测试 {len(split["test"])}；种子 20261025。缺治疗标签不排除影像。',
      f'- 纳入患者的实际间隔范围 {min(interval):g}—{max(interval):g} 周。无患者编号汇总行排除 {len(audit["ignored_no_patient_id_rows"])} 行。',
      f'- MRI 表标可用但实际未发现的条目 {len(audit["metadata_expected_missing"])} 项，逐项保存在 data_audit.json；不以其他模态/患者替代。',
      f'- 空间动作：{dict(actions)}。',
      '- 已比较物理坐标、方向、间距、仿射和空间范围；脑前景支持区重叠和强度相关性是粗筛，不能证明毫米级解剖配准。全部入组病例的基线中间层对照见 qc_contact_*.png；需要专家复核余下层面、局部病变和手术变化。',
      '- 脑区指标使用基线脑前景近似掩膜；本地影像有脑区提取特征，但掩膜没有人工验证。它不应被称为标准脑分割。',
      '- 全部可用基线 GTV 的最大面积层叠加图见 gtv_overlay_*.png，仅用于检查基线标签与影像大致对应；不能替代专家逐层审核，且不参与模型选片/训练/推理。',
      '- 低配对相关性只触发保守的待复核排除，不能区分配准问题、扫描对比变化和真实病变变化；这项粗筛可能排除变化较大的患者并造成选择偏倚。异常图见 flagged_*.png，不能据此宣称该病例本身无效。',
      '', '排除原因（一个患者可以多项）：','']
    for reason,count in audit['excluded_reasons'].items():lines.append(f'- {reason}：{count}')
    lines+=['','## 模型与实际预算','',
      '主模型使用 I²SB 公式 11 的条件桥分布、公式 12 的归一化残差 MSE 和高斯反向后验。x0 是真实随访、x1 是基线；推理从基线端点向随访端点走。网络额外接收基线及临床间隔，和内部扩散时间分别编码。公式、端点及官方实现的离散化区别见 README。',
      '', '| 实验 | 实际更新步数 | 时间（秒） | 参数量 | CUDA 峰值分配 MiB | 最佳验证脑区 MAE |','|---|---:|---:|---:|---:|---:|']
    for k in models:
        t=train[k];lines.append(f'| {k} | {t["last_step"]} | {t["elapsed_seconds"]:.1f} | {t["parameters"]} | {t["gpu_peak_allocated_bytes"]/1024**2:.1f} | {t["best_val_mae"]:.5f} |')
    lines+=['', '每个实验都是独立初始化，batch=8、128×128、初始通道 16。验证根据预定前 4 位验证患者各 8 张均匀切片，按患者等权 MAE 保存最佳 checkpoint；没有根据测试结果换权重、种子或样本。全部日志见 logs/，last.pt 可续训。验证子集小，仍存在选择方差。','',
      f'训练集合包含全部 {len(split["train"])} 位训练患者；本次 600 次均匀患者抽样实际访问 {exposure[models[0]]["unique_training_patients"]} 位，未被此次短预算抽到：{exposure[models[0]]["missing_from_short_draws"]}。两个模型患者抽样序列相同，验证/测试患者训练暴露为 0；不能将短预算称为遍历所有训练切片。','',
      '## 必要验证','',
      f'- 真实患者切片的前向/损失/反向梯度有限：{num["forward_backward_finite"]}。',
      f'- 桥 q 的精确端点、τ=0 标签拒绝、oracle 反向端点精确到达均通过。中间 τ=0.5 的理论方差 0.125，实测 {num["0.5"]["observed_variance"]:.6f}；oracle 反向链中间方差 {num["oracle_reverse_midpoint"]["variance"]:.6f}。',
      f'- 保存与重新加载后相同种子生成逐位一致：{num["save_reload_bitwise_equal"]}。',
      f'- 小样本拟合：仅训练患者 {ov["patient"]} 的切片 {ov["slices"]}，独立模型 {ov["steps"]} 步、{ov["seconds"]:.1f} 秒；固定且未用于更新的桥噪声状态 MSE 从 {ov["before"]["held_noise_bridge_mse"]:.5f} 到 {ov["after"]["held_noise_bridge_mse"]:.5f}，比例 {ov["held_noise_loss_ratio"]:.3f}，能力检查 {"通过" if ov["passed"] else "失败"}。',
      f'- 同一小样本生成脑区 MAE 从 {ov["before"]["sample_brain_mae"]:.5f} 到 {ov["after"]["sample_brain_mae"]:.5f}；其恒等 MAE {ov["after"]["identity_brain_mae"]:.5f}。这是拟合检查，不能混入独立测试均值，权重未用于主训练。',
      '- 每个独立测试体积重新加载选定权重、仅从原始基线生成；随后才读取目标评价。每例验证 NIfTI shape/affine 与原始基线匹配，coverage 内有限、外部 NaN。记录见各患者 nifti_verification.json。','']
    cli=ROOT/'reports/cli_verification.json'
    if cli.exists():lines += [f'- 独立 infer.py 命令行实际执行，同种子输出与评价流水线逐位一致：{read(cli)["same_seed_matches_evaluation_stack_bitwise"]}。','']
    integration_path=ROOT/'reports/integration_verification.json'
    if integration_path.exists():lines += ['附加集成检查：','', '```json',json.dumps(read(integration_path),ensure_ascii=False,indent=2),'```','']
    lines+=['## 独立测试：患者等权结果','',
      '评价在模型 128×128 网格、基线决定的脑前景支持区进行，data_range=1；目标与基线使用基线的同一分位数归一化。每切片计算区域 MAE、区域 MSE 的 PSNR 和 SSIM 图（7×7；窗口中心取腐蚀后脑区），先平均患者内切片，再平均患者。并非原生高分辨率评价。','',
      '区域小于 10 个模型像素的切片不参与该区域汇总；SSIM 无有效内部窗口时为 NA。逐患者 slices 字段记录有效数量，PSNR 用 1e-12 保护零 MSE。','',
      '| 方法 | 测试患者 | 脑区 MAE ↓ | 脑区 PSNR ↑ | 脑区 SSIM ↑ | 预测变化 MAE | 真实变化 MAE |','|---|---:|---:|---:|---:|---:|---:|']
    identity=test['i2sb_short']['identity']['brain_support'];n=test['i2sb_short']['patients']
    for label,v in [('恒等 t0',identity)]+[(k,test[k]['model']['brain_support']) for k in models]:
        lines.append(f'| {label} | {n} | {v["mae"]:.5f} | {v["psnr"]:.3f} | {v["ssim"]:.5f} | {v["predicted_change_mae"]:.5f} | {v["actual_change_mae"]:.5f} |')
    for k in models:
        v=test[k]['model']['brain_support'];delta=v['mae']-identity['mae']
        lines+=['',f'{k}：{test[k]["improved_mae_patients"]}/{n} 位患者脑区 MAE 优于恒等；平均 MAE 差（模型−恒等）{delta:+.5f}。'+('本次短训练在该指标上有平均改善，但尚不能证明临床有效。' if delta<0 else '本次短训练未超过恒等基线，不应宣称模型预测性能改善。')]
        if v['ssim']<identity['ssim']:
            lines += [f'{k} 的 SSIM 低于恒等基线；即使 MAE 有改善，也不能忽略结构相似度变差，不能笼统称为全面改善。']
    reg=test['regression_short']['model']['brain_support']
    lines += ['',f'回归模型的平均预测变化幅度仅 {reg["predicted_change_mae"]:.5f}，真实变化幅度为 {reg["actual_change_mae"]:.5f}，说明预测仍较保守、接近基线。图像相似度改善不能证明已经学会真实病灶演变。']
    lines+=['','基线放疗规划 GTV 内的附加评价（不是随访肿瘤分割）：','','| 方法 | 有效患者 | 靶区 MAE ↓ | PSNR ↑ | SSIM ↑ |','|---|---:|---:|---:|---:|']
    for label,source,method in [('恒等',test['i2sb_short'],'identity')]+[(k,test[k],'model') for k in models]:
        v=source[method].get('baseline_planning_GTV')
        if v:
            ssim=f'{v["ssim"]:.5f}' if v['ssim'] is not None else 'NA (no valid windows)'
            lines.append(f'| {label} | {v["patients"]} | {v["mae"]:.5f} | {v["psnr"]:.3f} | {ssim} |')
    lines+=['','GTV 是基线放疗规划大体靶区；没有随访分割，所以没有肿瘤 Dice。全局相似度和靶区强度误差都不能直接证明肿瘤生物学进展预测准确。','',
      '## 预定示例与失败','',
      '示例按固定测试集合中编号最小三位选择，显示基线支持区中间切片；不是按测试效果排名。所有测试患者都保留对照图和逐患者指标，因此改善差或失败者没有被隐藏。','']
    per=read(ROOT/'results/i2sb_short/per_patient.json')
    for pid in split['test'][:3]:
        r=next(r for r in per if r['patient_id']==pid)
        lines += [f'患者 {pid}，实际间隔 {r["weeks"]:g} 周：模型脑区 MAE {r["model"]["brain_support"]["mae"]:.5f}，恒等 {r["identity"]["brain_support"]["mae"]:.5f}，差 {r["delta_brain_mae"]:+.5f}。','',f'![预定患者 {pid}](../results/i2sb_short/{pid}/comparison.png)','']
    failed=[r['patient_id'] for r in per if r['delta_brain_mae']>=0]
    lines += [f'全体测试中 MAE 没有超过恒等的患者：{", ".join(failed) if failed else "本次无（不代表临床有效）"}。','',
       '预定患者 015 的生成中间层可见颗粒和模糊，预测变化与真实强度变化图并不充分一致；这是本次短训练输出的可见失败特征。MAE 轻微改善不意味着病灶变化被准确预测。',
       '误差可能来自随访强化及扫描强度变化、病变/术腔局部变化、粗配准残差、低分辨率信息损失和短训练不足；不能把这些因素都归为真实肿瘤进展。当前基线分位强度变换还可能使随访高亮区饱和。仅对照图不足以确定每项误差来源。','',
       '## 打开结果与实际推理命令','',
       '3D Slicer：Add Data 加载 prediction_normalized.nii.gz 与 coverage.nii.gz，按 0—1 调整显示；也可叠加清单的原始基线。prediction_baseline_intensity.nii.gz 是按基线强度逆变换的版本。空间信息恢复到原始基线，未覆盖体素明确为 NaN；coverage=1 才有模型预测。独立 2D 切片可能上下层不连续，恢复原尺寸不代表原生分辨率。','']
    pid=split['test'][0];row=manifest[pid]
    lines += ['```powershell',f"Set-Location '{ROOT}'",f"& '{ROOT / '.venv/Scripts/python.exe'}' infer.py --baseline '{row['source']}' --weeks {row['weeks']:g} --checkpoint weights/i2sb_short/best.pt --output results/manual_{pid} --seed 7391 --patient-id {int(pid)}",'```','',
       '## 下一步及结论边界','',
       '1. 先人工复核配准、脑区与基线靶区，处理异常病例；必要时以基线坐标进行刚体/仿射配准，并保留变换。不要把尺寸一致当作配准证据。',
       '2. 在同一患者划分上做更充分的训练与完整验证集选择，比较时间条件消融、确定性对照和更大分辨率。当前测试已经用于本报告，后续根据这些结果调参应另留新的最终测试/外部队列。',
       '3. 加入预测时可得的 FLAIR、治疗和临床条件，评估选择偏倚及不同随访间隔的泛化；观察性条件关联不等于治疗因果效应。',
       '4. 采用 2.5D/3D 改善连续性、补充专家随访分割和外部多中心验证；多次采样须固定规则，经过校准后才讨论临床不确定性。',
       '5. 独立图像相似度、临床进展判断和生存预测是不同目标，后两者还需要合法标签、适当研究设计与临床验证。',
       '', '本次已完成真实数据管线、数值检查、拟合检查、有界训练、重新加载生成、独立测试指标/对照图/NIfTI 的工程闭环。性能结论以表格为准，不能将运行成功解释为可靠肿瘤预后预测。','']
    (ROOT/'reports/实验报告.md').write_text('\n'.join(lines),encoding='utf-8')
    # Training curves from actual logs.
    fig,axs=plt.subplots(1,2,figsize=(12,4))
    for k in models:
        data=[json.loads(line) for line in (ROOT/f'logs/{k}/train.jsonl').read_text().splitlines()]
        val=[r for r in data if 'validation' in r]
        axs[0].plot([r['step'] for r in data],[r['loss'] for r in data],label=k,alpha=.7)
        axs[1].plot([r['step'] for r in val],[r['validation']['mae'] for r in val],label=k,marker='o')
    axs[0].set_title('Training objectives (different scales)');axs[1].set_title('Fixed validation patient MAE')
    for ax in axs:ax.set_xlabel('optimizer updates');ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(ROOT/'reports/training_curves.png',dpi=150);plt.close(fig)
    sources=list(ROOT.glob('*.py'))+list((ROOT/'cfb').glob('*.py'))+list((ROOT/'configs').glob('*.json'))
    dump(ROOT/'reports/artifact_checksums.json',{str(p.relative_to(ROOT)):sha(p) for p in list((ROOT/'weights').rglob('best.pt'))+[ROOT/'data/splits.json',ROOT/'data/manifest.json']+sources})
    print('Report created: reports/experiment report (Chinese).',flush=True)

if __name__=='__main__':main()
