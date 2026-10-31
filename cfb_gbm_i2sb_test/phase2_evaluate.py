"""Validation-only follow-up report; image access to old test set is blocked."""
import csv,time
from pathlib import Path
import numpy as np
import torch
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from cfb.common import ROOT,read,dump,sha,seed_all
from cfb.training import Cache,build,predict_stack,validate
from cfb.metrics import patient_metrics
from evaluate import plot_example
from phase2_run import install_test_guard
from infer import generate

OUT=ROOT/'reports/phase2_2026-10-31';DEST=ROOT/'results/phase2_2026-10-31'

def average(rows,key):
    result={}
    for region in ['brain_support','baseline_planning_GTV']:
        vals=[r[key][region] for r in rows if r[key].get(region)]
        if vals:
            result[region]={'patients':len(vals)}
            for metric in ['mae','psnr','ssim','predicted_change_mae','actual_change_mae']:
                values=[v[metric] for v in vals if v[metric] is not None]
                result[region][metric]=float(np.mean(values)) if values else None
    return result

def load(checkpoint,device):
    ck=torch.load(checkpoint,map_location=device,weights_only=False);cfg=ck['config'].copy()
    net,bridge=build(cfg,cfg['kind'],device);net.load_state_dict(ck['model']);net.eval()
    return net,bridge,cfg,ck

def full_eval(name,checkpoint,ids,manifest,cache,device,examples):
    existing=DEST/name/'summary.json'
    if existing.exists():
        saved=read(existing)
        if (saved.get('checkpoint_sha256')==sha(checkpoint) and saved.get('splits_sha256')==sha(ROOT/'data/splits.json')
            and saved.get('manifest_sha256')==sha(ROOT/'data/manifest.json') and {r['patient_id'] for r in read(DEST/name/'per_patient.json')}==set(ids)
            and all((DEST/name/p/'comparison.png').exists() for p in examples)):
            print('REUSE COMPLETED VALIDATION',name,flush=True);return saved
    net,bridge,cfg,ck=load(checkpoint,device)
    cfg.update(val_patients=24,val_slices=16,validation_min_region_pixels=10)
    selection=validate(net,bridge,cfg,ids,manifest,cache,device)
    folder=DEST/name;folder.mkdir(exist_ok=True,parents=True);records=[]
    for pid in ids:
        d=cache.get(pid);b=d['baseline'];t=d['target'];m=d['mask']>.5;gtv=d['gtv']>.5
        # Only baseline and clinical weeks enter prediction; targets used subsequently.
        pred=predict_stack(net,bridge,b,manifest[pid]['weeks'],cfg,device,int(pid))
        model=patient_metrics(pred,t,m,b,gtv);identity=patient_metrics(b,t,m,b,gtv)
        records.append(dict(patient_id=pid,weeks=manifest[pid]['weeks'],model=model,identity=identity,delta_mae=model['brain_support']['mae']-identity['brain_support']['mae']))
        if pid in examples:
            case=folder/pid;case.mkdir(exist_ok=True)
            np.save(case/'prediction_stack.npy',pred)
            plot_example(pid,manifest[pid]['weeks'],b,t,pred,m,case/'comparison.png')
    report=dict(name=name,cohort='validation, not independent test',patients=len(ids),checkpoint=str(checkpoint),checkpoint_sha256=sha(checkpoint),step=ck['step'],
        splits_sha256=sha(ROOT/'data/splits.json'),manifest_sha256=sha(ROOT/'data/manifest.json'),
        selection_16_slices=selection,model=average(records,'model'),identity=average(records,'identity'),improved_mae_patients=sum(r['delta_mae']<0 for r in records),
        improved_ssim_patients=sum(r['model']['brain_support']['ssim']>r['identity']['brain_support']['ssim'] for r in records))
    dump(folder/'per_patient.json',records);dump(folder/'summary.json',report)
    with (folder/'per_patient.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['patient','weeks','model_mae','identity_mae','delta_mae','model_psnr','identity_psnr','model_ssim','identity_ssim'])
        for r in records:
            a=r['model']['brain_support'];b=r['identity']['brain_support'];writer.writerow([r['patient_id'],r['weeks'],a['mae'],b['mae'],r['delta_mae'],a['psnr'],b['psnr'],a['ssim'],b['ssim']])
    print('FULL VAL',name,report['model']['brain_support'],flush=True);return report

def diagnostics(name,checkpoint,ids,manifest,cache,device):
    net,bridge,cfg,ck=load(checkpoint,device);rng=np.random.default_rng(20261031)
    weeks=np.array([manifest[p]['weeks'] for p in ids]);permuted=weeks[rng.permutation(len(weeks))]
    constant=float(np.expm1(cfg['week_mean']));rows=[]
    for i,pid in enumerate(ids):
        d=cache.get(pid);z=np.unique(np.linspace(0,len(d['baseline'])-1,16).round().astype(int));b=d['baseline'][z];t=d['target'][z];m=d['mask'][z]>.5
        ps={};scores={}
        for mode,w in [('correct',weeks[i]),('permuted',permuted[i]),('constant_train',constant)]:
            ps[mode]=predict_stack(net,bridge,b,float(w),cfg,device,int(pid))
            scores[mode]=patient_metrics(ps[mode],t,m,b)['brain_support']
        row=dict(patient=pid,weeks=float(weeks[i]),permuted_weeks=float(permuted[i]),scores=scores,
            shuffled_prediction_difference=float(np.abs(ps['permuted']-ps['correct'])[m].mean()),
            constant_prediction_difference=float(np.abs(ps['constant_train']-ps['correct'])[m].mean()))
        if cfg['kind']=='i2sb':
            sample_scores=[scores['correct']['mae']];diffs=[]
            for seed in [7392,7393]:
                cc=cfg.copy();cc['sampling_seed']=seed;p=predict_stack(net,bridge,b,float(weeks[i]),cc,device,int(pid))
                sample_scores.append(patient_metrics(p,t,m,b)['brain_support']['mae']);diffs.append(float(np.abs(p-ps['correct'])[m].mean()))
            row.update(sampling_mae_by_seed=sample_scores,sampling_difference_mae=float(np.mean(diffs)))
        rows.append(row)
    report=dict(protocol='all 24 validation patients, fixed 16 evenly spaced baseline slices; identical noise when changing clinical time; constant from TRAIN log-week mean',
        permuted_interval_changed_patients=int(np.count_nonzero(permuted!=weeks)),constant_interval_weeks=constant,
        seeds=[7391,7392,7393] if cfg['kind']=='i2sb' else [],sample_selection='none; all predetermined samples retained as statistics; no best-of-N',
        scores={mode:{metric:float(np.mean([r['scores'][mode][metric] for r in rows])) for metric in ['mae','psnr','ssim']} for mode in ['correct','permuted','constant_train']},
        mean_shuffled_prediction_difference=float(np.mean([r['shuffled_prediction_difference'] for r in rows])),
        mean_constant_prediction_difference=float(np.mean([r['constant_prediction_difference'] for r in rows])),patients=rows,
        warning='Validation ablation only. No causal interpretation or calibrated uncertainty.')
    if cfg['kind']=='i2sb':
        values=np.array([r['sampling_mae_by_seed'] for r in rows]);report['mean_patient_mae_by_sampling_seed']=values.mean(0).tolist()
        report['sampling_difference_mae']=float(np.mean([r['sampling_difference_mae'] for r in rows]))
    dump(DEST/name/'diagnostics.json',report);return report

def main():
    install_test_guard();seed_all(20261031);device='cuda' if torch.cuda.is_available() else 'cpu'
    plan=read(OUT/'plan.json');assert (OUT/'training_completed.json').exists()
    assert sha(ROOT/'data/splits.json')==plan['splits_sha256'] and sha(ROOT/'data/manifest.json')==plan['manifest_sha256']
    split=read(ROOT/'data/splits.json');ids=split['val'];manifest={r['patient_id']:r for r in read(ROOT/'data/manifest.json')};cache=Cache();DEST.mkdir(exist_ok=True)
    reports={}
    for kind in ['i2sb','regression']:
        name=f'{kind}_original';reports[name]=full_eval(name,ROOT/f'weights/{kind}_short/best.pt',ids,manifest,cache,device,[])
    for r in plan['runs']:
        reports[r['name']]=full_eval(r['name'],ROOT/f'weights/{r["name"]}/best.pt',ids,manifest,cache,device,ids[:3])
    chosen={kind:min([r['name'] for r in plan['runs'] if r['kind']==kind],key=lambda n:reports[n]['selection_16_slices']['mae']) for kind in ['i2sb','regression']}
    dump(OUT/'selected_runs.json',dict(rule='minimum predeclared validation 16-slice MAE among seeds, not full-volume metrics or test',runs=chosen))
    diagnostic={}
    for kind,name in chosen.items():
        ck=ROOT/f'weights/{name}/best.pt';diagnostic[kind]=diagnostics(name,ck,ids,manifest,cache,device)
        pid=ids[0];case=DEST/name/pid
        # Standalone inference reads raw baseline only; verify original space after reload.
        pred,raw_baseline,_,_=generate(manifest[pid]['source'],manifest[pid]['weeks'],ck,case/'native',patient_id=int(pid))
        cached_prediction=np.load(case/'prediction_stack.npy')
        assert np.isfinite(pred).all()
        assert np.allclose(raw_baseline,cache.get(pid)['baseline'],atol=.00025)
        precision=dict(raw_vs_float16_cache_prediction_mae=float(np.abs(pred-cached_prediction).mean()),
            raw_vs_float16_cache_prediction_max_difference=float(np.abs(pred-cached_prediction).max()),
            note='Native inference reprocesses raw baseline in float32; cached validation uses float16 baseline, so bitwise equality is not expected')
        import nibabel as nib
        output=nib.load(case/'native/prediction_normalized.nii.gz');original=nib.load(manifest[pid]['source'])
        coverage=nib.load(case/'native/coverage.nii.gz').get_fdata()>0;values=output.get_fdata(dtype=np.float32)
        assert output.shape==original.shape and np.allclose(output.affine,original.affine)
        assert np.isfinite(values[coverage]).all() and np.isnan(values[~coverage]).all()
        dump(case/'native/spatial_verification.json',dict(shape_matches=True,affine_matches=True,finite_inside_coverage=True,nan_outside_coverage=True,precision=precision))
    for r in plan['runs']:
        if r['resume']:assert sha(r['resume'])==plan['parent_sha256'][r['name']]
    dump(OUT/'comparison.json',dict(cohort='validation only; not independent evidence',results=reports,chosen=chosen,diagnostics={k:{x:y for x,y in v.items() if x!='patients'} for k,v in diagnostic.items()},test_image_access_blocked=True))
    lines=['# 第二轮有界训练报告（2026-10-31）','',
        '本轮仅使用训练集和验证集；原测试集此前已经查看，本轮通过文件访问检查禁止读取其影像缓存和原始影像。以下全部为验证结果，不能与第一轮独立测试数字直接比较。','',
        '保留 v1 预处理、I²SB 桥目标、网络规模和学习率；第一种子从 600 步 last.pt 延续，第二种子从头训练。每个运行总目标 5,000 步、最大 8 分钟。验证扩至全部 24 位患者，每位固定 16 张基线规则切片；选择规则改变时重新给起始 checkpoint 打分，不继承旧最佳分数。','',
        '## 实际预算与全覆盖验证结果','',
        '表中 MAE/PSNR/SSIM 在全部基线覆盖的验证切片上先按切片、再按患者等权汇总；最终权重仍按预先规定的 16 张切片验证 MAE 选出。','',
        '| 运行 | 实际训练终步 | 选择步 | 全覆盖 MAE | PSNR | SSIM | MAE 胜恒等患者 |','|---|---:|---:|---:|---:|---:|---:|']
    identity=reports['i2sb_original']['identity']['brain_support']
    lines.append(f'| 恒等基线 | — | — | {identity["mae"]:.5f} | {identity["psnr"]:.3f} | {identity["ssim"]:.5f} | — |')
    for name,rep in reports.items():
        summary=read(ROOT/f'logs/{name}/summary.json') if name in [r['name'] for r in plan['runs']] else None
        m=rep['model']['brain_support'];lines.append(f'| {name} | {summary["last_step"] if summary else 600} | {rep["step"]} | {m["mae"]:.5f} | {m["psnr"]:.3f} | {m["ssim"]:.5f} | {rep["improved_mae_patients"]}/24 |')
    lines+=['','## 重复训练与训练充分性','']
    for kind in ['i2sb','regression']:
        names=[r['name'] for r in plan['runs'] if r['kind']==kind];values=[reports[n]['model']['brain_support']['mae'] for n in names]
        lines.append(f'- {kind}：两个种子的全覆盖验证 MAE 为 {values}，均值 {np.mean(values):.5f}，样本标准差 {np.std(values,ddof=1):.5f}。只有两次运行，不能据此充分刻画训练不确定性。')
    for r in plan['runs']:
        history=[__import__('json').loads(line) for line in (ROOT/f'logs/{r["name"]}/train.jsonl').read_text().splitlines()]
        summary=read(ROOT/f'logs/{r["name"]}/summary.json');seen={x['patient'] for x in history}
        lines.append(f'- {r["name"]}：新增 {len(history)} 步，{summary["elapsed_seconds"]:.1f} 秒；新增阶段访问 {len(seen)}/112 位训练患者；没有验证或测试患者进入训练。')
        assert seen<=set(split['train'])
    lines+=['','## 临床时间与随机采样诊断','',
        '本项仍使用全部验证患者、各 16 张固定切片。打乱/固定时间时保持同一图像采样噪声；固定时间由训练集 log(1+weeks) 均值反变换得到。','',
        '| 模型 | 正确间隔 MAE | 打乱间隔 MAE | 固定间隔 MAE |','|---|---:|---:|---:|']
    for kind,d in diagnostic.items():
        lines.append(f'| {kind} | {d["scores"]["correct"]["mae"]:.5f} | {d["scores"]["permuted"]["mae"]:.5f} | {d["scores"]["constant_train"]["mae"]:.5f} |')
    d=diagnostic['i2sb']
    lines.append(f'\nI²SB 预设采样种子 7391/7392/7393 的患者平均 MAE：{d["mean_patient_mae_by_sampling_seed"]}。均报告，不根据目标挑选最好样本；随机输出差异不是校准的临床不确定性。\n')
    lines+=['','## 预处理与限制','',
        '缓存模型网格内平均高端饱和比例：训练 0.91%、验证 0.55%；003、259 两个训练患者超过 5%。诊断图和原始数据抽查另存 cache_qc.json、raw_qc.json、qc_selected.png。目标强度变化依然可能混合扫描差异与生物学变化。本轮没有根据验证/测试目标逐例匹配强度，也没有据此重定义裁剪。空间指标和中间层人工可视化只属于粗查，不能替代专家配准确认。','',
        '验证患者参与权重和种子选择，因此这些改善不是新的独立测试证据；原测试集继续封存，后续定型需要外部/新最终测试。预测变化幅度不等于正确病灶演变；无随访分割，不报告肿瘤 Dice。','',
        '## 结果位置','']
    for kind,name in chosen.items():
        m=reports[name]['model']['brain_support'];old=reports[kind+'_original']['model']['brain_support']
        lines.append(f'- {kind} 选定 {name}：相对旧模型同一验证队列的 MAE 差 {m["mae"]-old["mae"]:+.5f}；预测变化幅度 {m["predicted_change_mae"]:.5f}，真实变化幅度 {m["actual_change_mae"]:.5f}。')
        if m['ssim']<identity['ssim']:
            lines.append('该模型的全覆盖验证 SSIM 仍低于恒等基线；即使 MAE 下降，也不能称为结构质量全面改善。')
        lines.append(f'预测/真实强度变化幅度比约 {m["predicted_change_mae"]/m["actual_change_mae"]:.1%}；该比例不是预测准确率或捕获的肿瘤变化比例。')
        d=diagnostic[kind]
        if d['scores']['correct']['mae']>=d['scores']['permuted']['mae']:
            lines.append('推理时打乱间隔未使该诊断的平均 MAE 变差，本结果不支持模型已经有效利用真实时间；还需独立的训练条件消融和更可靠标签。')
        lines.append('本轮预定示例仍可见细节模糊或局部变化不一致；指标改善不能证明病灶演变正确。')
        for pid in ids[:3]:lines+=['',f'![验证病例 {pid} / {kind}](../../results/phase2_2026-10-31/{name}/{pid}/comparison.png)','']
        lines.append(f'验证患者 {ids[0]} 的原生空间 NIfTI 在 results/phase2_2026-10-31/{name}/{ids[0]}/native/；只加载基线重建并检查 affine、coverage 和 NaN。')
    row=manifest[ids[0]];name=chosen['i2sb']
    lines+=['','## 使用新权重的独立推理命令','', '```powershell',
        f"Set-Location '{ROOT}'",
        f"& '{ROOT / '.venv/Scripts/python.exe'}' infer.py --baseline '{row['source']}' --weeks {row['weeks']:g} --checkpoint 'weights/{name}/best.pt' --output 'results/phase2_manual_{ids[0]}' --seed 7391 --patient-id {int(ids[0])}",
        '```','', '3D Slicer 用 Add Data 加载原生空间预测与 coverage；只有 coverage=1 的体素有效。生成图为 2D 切片重建，仍可能有三维不连续和升采样模糊。']
    (OUT/'第二轮训练报告.md').write_text('\n'.join(lines),encoding='utf-8')
    fig,axs=plt.subplots(1,2,figsize=(13,4))
    for r in plan['runs']:
        history=[__import__('json').loads(line) for line in (ROOT/f'logs/{r["name"]}/train.jsonl').read_text().splitlines()];v=[x for x in history if 'validation' in x]
        axs[0].plot([x['step'] for x in v],[x['validation']['mae'] for x in v],marker='.',label=r['name'])
        axs[1].plot([x['step'] for x in history],[x['loss'] for x in history],alpha=.6,label=r['name'])
    axs[0].set_title('All 24 validation patients, 16 slices each');axs[1].set_title('Training objectives differ between methods')
    for ax in axs:ax.legend(fontsize=7);ax.grid(alpha=.2);ax.set_xlabel('total optimizer updates')
    fig.tight_layout();fig.savefig(OUT/'training_curves.png',dpi=140);plt.close(fig)
    dump(OUT/'evaluation_completed.json',dict(cohort='validation only',test_images_read=False,selected=chosen,source_split_sha256=sha(ROOT/'data/splits.json')))
    print('PHASE2 EVALUATION COMPLETE',chosen,flush=True)

if __name__=='__main__':main()
