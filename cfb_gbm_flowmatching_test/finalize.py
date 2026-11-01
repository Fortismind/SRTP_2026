from fm.common import *
import csv,subprocess,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    audit=read(ROOT/'reports/data_audit.json');checks=read(ROOT/'reports/checks.json');results=read(ROOT/'reports/test_summary.json');comparison=read(ROOT/'reports/comparison.json');env=read(ROOT/'reports/environment.json');logs={k:read(ROOT/'logs'/f'{k}.json') for k in KINDS}
    inventory=read(ROOT/'reports/file_inventory.json')
    lines=['# MRI 起点 Flow Matching：有界实验报告','',
    '本轮仅研究同患者基线增强 T1 + 实际周数 → 随访增强 T1。t0 是数据集基线，不自动等于术前或所有治疗之前。原 I²SB 工程和 E 盘数据只读。历史测试集已在旧实验查看过，本轮属于探索性比较。','',
    '## 数学与实现','',
    '`zτ=(1−τ)Y+τB`，`u=B−Y`，每次调用都传入原始 B、基线 GTV、标注可用指示、τ 和 weeks。τ=1 为 B，τ=0 为 Y。训练使用 brain 内每样本归一化 MSE；12.5% 样本强制 τ=1。`Yhatτ=zτ−τv` 仅为训练单点端点估计。主结果从 B 以 Euler 16 步完整积分，NFE=16，不截断中间状态；仅在最终输出 clamp 到 [0,1]，指标、图和 NIfTI 一致。Heun 16 步 NFE=32。','',
    '主模型为确定性监督配对转换；不保证精确恢复每条插值轨迹或配对耦合。中间状态不代表临床某天，不是肿瘤生长模拟。Noise 对照仅在起点改为标准高斯，路径与速度相应改变；固定 seed=7391+患者号×10000+批次首层索引、batch=8，不以目标挑样本。','',
    'GTV 是基线放疗规划靶区，不是随访分割。物理网格必须一致才使用；5 mm 膨胀先在原生空间按真实间距计算，再最近邻缩放。缺失 GTV 仍保留患者，全局损失照常参与；空标注 available=1，缺失 available=0。ROI L1 按每样本区域归一化，再平均有效样本；λ=0.1 预先固定，不进行测试调参。ROI 外仍能变化，未硬复制。未来分割未经确认，未添加 Dice 或未来掩膜输入。','',
    '## 当前数据核查','',
    f"全目录文件名重新扫描：后缀计数 {inventory['suffix_counts']}。其中精确 .nii.gz 为当前 NIfTI 数；.~#0 / .~@0 后缀为额外文件，不作为新影像或新患者纳入。候选标签均在 t0，未发现可靠的随访分割，详见 label_inventory.json。",
    f"重新处理固定划分患者 {audit['rechecked_fixed_split_patients']} 位，有效划分 {audit['effective_sizes']}；新排除 {audit['exclusions']}。GTV 状态 {audit['mask_status_counts']}。完整空间信息、相关性和支持区重叠见 cache/*.json、reports/data_audit.json。GTV 叠加图覆盖所有有效标注病例。",
    '复用旧清单与划分文件，不重新随机划分；本轮核查对象是固定划分的入组病例，264 行为来源清单行数，不能表述成重新发现全部原始患者。旧强度缓存仅在原文件签名、完整物理网格及预处理源码一致时只读复用，来源哈希记录在各 cache JSON；初始原始重算缓存逐元素核对一致。标注重新读取，缓存写新项目。基线确定裁剪、支持区与 0.5/99.5 正强度分位数尺度，两时点共同使用；不对随访单独强度匹配。饱和比例为模型网格脑支持区中目标取值达到 0/1 的比例，扫描对比变化与截断可能混入疾病变化。物理网格一致和粗相关性不能证明局部精确配准，重采样不称为配准。',
    f"只使用 weeks，训练 log1p 周数统计量为 {read(ROOT/'data/week_stats.json')}。临床可选字段缺失计数 {audit['clinical_missing_counts']}；剂量/分次/延迟的预测可用时点未验证，全部排除，没有生存输入。",'',
    '已目视抽查 003 与 GTV/脑支持交集最小的207号叠加图；207 的 GTV 有约15.8%落在近似支持区外，不能把自动支持区边缘当解剖真值。模型网格目标饱和率全患者均值约1.18%。仅为粗查，详见 visual_review.json，不代替专家逐层复核。',
    '## 环境与预算','',f"Python {env['python'].split()[0]}，PyTorch {env['torch']}，CUDA {env['cuda']}，{env['gpu']}，{env['memory_GiB']:.2f} GiB。项目局部 venv 只读复用已安装库，不修改既有环境。",
    '正式配置每模型最多 4000 更新或 900 秒，先到即停；验证时间计入预算，验证临界点及 checkpoint 写出可能轻微超过墙钟上限。batch=8，通道16，AdamW lr=2e-4。全部模型独立同种子初始化、同患者抽样与配对翻转规则；从全部训练患者均匀抽患者再抽支持区切片。验证使用全部验证患者，各取最多8张由基线支持区均匀决定的切片；按患者等权 brain MAE 选权重，所有模型一致。测试结果不参与选择。','',
    '| 模型 | 更新 | 秒(含验证) | 更新秒均值 | 参数 | 峰值MiB | 验证MAE | ROI有效比例 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    participation={k:dict(nonempty_roi_sample_fraction=l['roi_sample_fraction'],effective_roi_loss_sample_fraction=l['roi_sample_fraction'] if k in ['direct_roi','noise_roi','regression'] else 0.,lambda_roi=.1 if k in ['direct_roi','noise_roi','regression'] else 0.) for k,l in logs.items()}
    write(ROOT/'reports/roi_loss_participation.json',participation)
    selections={k:dict(last_update=l['updates'],selected_update=torch.load(ROOT/'weights'/k/'best.pt',map_location='cpu',weights_only=False)['step'],validation_mae=l['best_validation_mae']) for k,l in logs.items()}
    write(ROOT/'reports/checkpoint_selection.json',selections)
    for k,l in logs.items():lines.append(f"|{k}|{l['updates']}|{l['seconds']:.1f}|{l['update_seconds_mean']:.4f}|{l['parameters']}|{l['peak_MiB']:.1f}|{l['best_validation_mae']:.5f}|{participation[k]['effective_roi_loss_sample_fraction']:.3f}|")
    lines+=['','各分支实际选中的更新步数：'+str({k:v['selected_update'] for k,v in selections.items()})+'。']
    lines+=['','日志原字段 roi_sample_fraction 统计抽样切片中非空 ROI 比例；只有 λ>0 的分支实际参与区域损失。表格给出实际参与比例，派生记录见 roi_loss_participation.json，未改写原训练日志。']
    lines+=['','## 必要检查','',json.dumps(checks,ensure_ascii=False,indent=2),'',
    '标注契约检查见 mask_contract.json：缺失与有效空标注的 available 不同；各向异性网格中5mm膨胀与物理距离解析结果一致，配对变换坐标一致。纯推理入口不接受 target；每个正式测试病例生成时主动禁止非基线/GTV NIfTI 读取和所有 np.load 配对缓存读取，记录见 inference_guard.json。目标缓存由外层评价器加载用于指标，不传入生成函数；生成函数受守卫保护，期间禁止任何配对缓存或随访影像读取。每个生成体积已核对 shape/affine/qform/sform、coverage 内有限、外 NaN。恢复尺寸不等于恢复原始分辨率，2D 切片可能不连续。','',
    '## 患者等权测试结果','',
    '先按患者内有效切片平均，再对患者等权平均。支持区是近似脑前景；MAE、PSNR 和 SSIM 在 [0,1] 模型网格评价，SSIM 7×7 窗中心要求脑支持区腐蚀3像素内，区域少于10像素的层跳过，空区域记缺失。PSNR 每层由区域 MSE 计算后平均。ROI 与 GTV 周围5mm的指标和有效患者数见各 summary.json。','',
    '| 模型 | 脑MAE↓ | PSNR↑ | SSIM↑ | 预测变化幅度 | 真实变化幅度 | GTV MAE |','|---|---:|---:|---:|---:|---:|---:|']
    for k,r in results.items():
        b=r['brain_support'];g=r['baseline_planning_GTV'].get('mae',float('nan'));lines.append(f"|{k}|{b['mae']:.5f}|{b['psnr']:.3f}|{b['ssim']:.5f}|{b['predicted_change_mae']:.5f}|{b['actual_change_mae']:.5f}|{g:.5f}|")
    lines+=['','基线规划 GTV 内指标（不是随访肿瘤真值）：','', '|模型|有效患者|MAE↓|SSIM↑|预测变化|真实变化|','|---|---:|---:|---:|---:|---:|']
    for k,r in results.items():
        g=r['baseline_planning_GTV'];lines.append(f"|{k}|{g['patients']}|{g['mae']:.5f}|{g['ssim']:.5f}|{g['predicted_change_mae']:.5f}|{g['actual_change_mae']:.5f}|")
    lines+=['','主模型的 GTV MAE 有小幅改善，但 GTV SSIM 低于 Identity，区域预测变化也偏大，不能笼统宣称结构或病灶预测改善。','', '各方法平均每患者推理秒数与每切片实际 NFE：','']
    for k,r in results.items():lines.append(f"- {k}: {r['runtime']['mean_patient_inference_seconds']:.2f} 秒，NFE={r['runtime']['nfe_per_slice']}。耗时包括积分与输出恢复/写盘，不含初始基线预处理；identity 为直接读取，记0。")
    lines+=['','主改进模型 direct_roi 相对各对照的脑MAE差（主模型−对照，负值更好）；GTV、ROI 与周边的逐患者差值见 comparison.json：','']
    for k,v in comparison.items():lines.append(f"- {k}: 均值差 {v['mean_mae_difference']:+.5f}，改善 {v['improved_patients']}/{len(v['patient_differences'])} 人。")
    main_mae=results['direct_roi']['brain_support']['mae'];id_mae=results['identity']['brain_support']['mae']
    regression_mae=results['regression']['brain_support']['mae']
    lines+=['',f"主模型脑区 MAE {main_mae:.5f}，残差回归 {regression_mae:.5f}；主模型比回归高 {main_mae-regression_mae:+.5f}，仅 {comparison['regression']['improved_patients']}/{len(comparison['regression']['patient_differences'])} 位患者优于回归。本轮主模型未超过匹配的小型残差回归，不支持 Flow Matching 优于简单回归的结论。",'实际独立 infer.py 子进程命令行已执行，固定病例015完整输出与评价逐位一致，训练暴露不含验证/测试患者，详见 cli_verification.json。']
    lines+=['',f"本次主模型{'优于' if main_mae<id_mae else '未优于'}恒等基线的平均脑 MAE；这不代表病灶预测可靠。各简单对照是否更好应同时查看表格。单种子、有界预算不足以证明收敛或稳定优势，不作严格算法排名。旧 I²SB 预算、预处理细节及当前验证流程不完全匹配，未并入排名。",'',
    '变化残差 L1 与相同区域的随访影像 L1 完全相同，不作独立证据。额外记录变化相关性（任一标准差≤1e-6记缺失）与方向一致率（真实变化绝对值>0.02 的像素）；方向与强度变化不能等同于肿瘤体积变化。无真实随访分割，不报肿瘤 Dice 或用固定 GTV 体积冒充未来体积。','',
    '全部测试病例和所有方法均保存图、患者指标；固定展示切片由基线支持区三等分中间点确定，GTV 最大层只用于标签质检。主模型相对 Identity 最差的病例（事后失败描述，不参与权重选择）：']
    worst=sorted(comparison['identity']['patient_differences'].items(),key=lambda x:x[1],reverse=True)[:3]
    for pid,d in worst:lines.append(f'- {pid}: MAE差 {d:+.5f}，见 results/direct_roi/{pid}/comparison.png。')
    lines+=['','目视检查固定病例015：无掩膜模型存在模糊；ROI 主模型出现整体变暗、范围过广的预测变化及模型平面边缘伪影。021、151 是相对 Identity 的主要失败病例，真实与预测的主要亮度变化方向不匹配，结构细节也不充分。原生输出只在 coverage 内保留生成值，但这不能消除支持区内的强度偏差。图像误差可能包含扫描强度混杂、真实变化与模型偏差，不能仅凭图将其归因于肿瘤进展。','', '固定示例取患者编号最小三位（非按预测效果选择）：','']
    for pid in sorted(read(ROOT/'data/effective_splits.json')['test'])[:3]:lines.append(f'![预定病例 {pid}](../results/direct_roi/{pid}/comparison.png)\n')
    lines+=['','## 验证积分检查','', '|模型|求解器|步数|NFE|验证MAE|','|---|---|---:|---:|---:|']
    for v in read(ROOT/'reports/solver_stability.json'):lines.append(f"|{v['kind']}|{v['solver']}|{v['steps']}|{v['nfe']}|{v['validation_mae']:.5f}|")
    lines+=['','各配置均保持有限输出，但增加步数或使用 Heun 没有单调改善指标；噪声对照对积分配置更敏感。这提示学习向量场和离散化误差仍有限制，不能把数值有限当作收敛。最终测试协议始终 Euler16，未依据测试调整。正式权重 best.pt 用于评价；last.pt 含优化器、步数、随机状态和抽样状态，支持续训；小样本拟合权重完全独立。训练曲线见 training_curves.png。','',
    '限制：分位数饱和、扫描强度混杂、粗空间筛查及历史入组选择偏倚、GTV 规划语义与缺失、2D 不连续、单种子、验证切片覆盖不足和探索性历史测试集。该原型不是 SD3、Brain-WM、MOTFM 或 I²SB 的完整复现，不宣称新算法、校准不确定性或临床可用性。后续可在预注册预算下延长训练、增加种子、完善配准和专家病灶评价，再考虑2.5D/3D；不会自动无界延长。']
    (ROOT/'reports/实验报告.md').write_text('\n'.join(lines),encoding='utf-8')
    fig,axs=plt.subplots(1,2,figsize=(12,4))
    for k,l in logs.items():
        h=l['history'];axs[0].plot([v['step'] for v in h],[v['loss'] for v in h],label=k);axs[1].plot([v['step'] for v in h],[v['validation_mae'] for v in h],label=k)
    axs[0].set_title('Training objective (different objectives)');axs[1].set_title('Full validation patient-equal brain MAE');axs[1].legend();fig.tight_layout();fig.savefig(ROOT/'reports/training_curves.png');plt.close(fig)
    originals=read(ROOT/'reports/original_artifact_hashes.json');unchanged={p:sha(p)==h for p,h in originals.items()};assert all(unchanged.values())
    expected=set(read(ROOT/'data/effective_splits.json')['test'])
    assert all(set(read(ROOT/'results'/k/'per_patient.json'))==expected for k in ['identity']+KINDS)
    guards=read(ROOT/'reports/inference_guard.json');assert len(guards)==len(expected)*len(KINDS) and all(v['cache_reads']==0 and v['guard_rejection_selftest'] for v in guards)
    spatial=list((ROOT/'results').glob('*/*/spatial_verification.json'));assert len(spatial)==len(expected)*len(KINDS)
    cli=read(ROOT/'reports/cli_verification.json');assert cli['full_ode_matches_evaluation_bitwise']
    write(ROOT/'reports/delivery_verification.json',dict(original_tracked_artifacts_unchanged=unchanged,training_patient_sequences_equal=len(set(v['sample_sequence_sha256'] for v in logs.values()))==1,all_test_patients=len(expected),all_arms=['identity']+KINDS,guarded_generation_cases=len(guards),verified_native_prediction_cases=len(spatial),actual_cli_bitwise_match=True))
    write(ROOT/'reports/source_checksums.json',{str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*.py') if '.venv' not in p.parts})
    print('FINALIZED',flush=True)
if __name__=='__main__':main()
