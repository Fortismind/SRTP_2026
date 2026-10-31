"""Finalize report layout and archive postprocessing sources, no model reruns."""
import shutil,re
from cfb.common import ROOT,read,dump,sha

out=ROOT/'reports/phase2_2026-10-31';file=out/'第二轮训练报告.md';text=file.read_text(encoding='utf-8')
text=text.split('\n## 本轮阶段判断')[0].rstrip()
lines=text.splitlines();paragraphs=[s for s in lines if s.startswith('I²SB 预设采样种子')]
text='\n'.join(s for s in lines if not s.startswith('I²SB 预设采样种子'))
if paragraphs:text=text.replace('## 预处理与限制','\n'.join(paragraphs)+'\n\n## 预处理与限制')
text=re.sub(r'(?m)(^\|[^\n]*\|\n)(?:[ \t]*\n)+(?=\|)',r'\1',text)
comparison=read(out/'comparison.json');interpretation=['','## 本轮阶段判断','']
for kind in ['i2sb','regression']:
    d=comparison['diagnostics'][kind];correct=d['scores']['correct']['mae'];shuffle=d['scores']['permuted']['mae']
    interpretation.append(f'- {kind}：打乱间隔使固定切片验证 MAE 改变 {shuffle-correct:+.5f}（相对正确间隔约 {(shuffle/correct-1)*100:+.2f}%）；效果较小，不能仅据此证明临床时间预测有效。')
interpretation += ['- 两个种子的新模型在同一验证队列的 MAE 均比旧模型低，但验证集已参与权重选择，不能宣称独立测试性能已提高。',
    '- 按预定 MAE 规则选中的 I²SB 权重来自 4,500 步，SSIM 仍低于恒等；第二个种子的 SSIM 较好，说明不同指标与随机种子存在取舍，未事后改用 SSIM 挑选样本或权重。',
    '- 回归对照目前更稳定，但预定图像仍有模糊，预测变化仍小于真实强度变化。进一步工作应针对结构质量、强度差异和有效临床条件，而不只是继续堆训练步数。','']
text+='\n'+'\n'.join(interpretation);file.write_text(text,encoding='utf-8')
sources=list(ROOT.glob('phase2*.py'))+[ROOT/'test_phase2.py',ROOT/'cfb/training.py',ROOT/'README_PHASE2.md']
for source in sources:
    destination=out/'final_source_snapshot'/source.relative_to(ROOT);destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
dump(out/'final_sources_sha256.json',{str(p.relative_to(ROOT)):sha(p) for p in sources})
print('Phase2 report finalized without repeating training or inference.')
