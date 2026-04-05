"""
FridayDream - 每周五收盘后自动运行，整理本周记忆

基于 Claude Code autoDream 设计，适合 A股量化场景
"""
import os
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from skill_context import SkillContext


MEMORY_DIR = r"E:\.openclaw\memory"
MEMORY_FILE = r"E:\.openclaw\MEMORY.md"
DATA_DIR = r"E:\.openclaw\data_bus"
PORTFOLIO_FILE = r"E:\.openclaw\data_bus\portfolio.json"


class FridayDream:
    """
    每周五收盘后运行的记忆整合 agent

    4阶段：
      Orient → Gather → Consolidate → Prune
    """

    def __init__(self, ctx: SkillContext):
        self.ctx = ctx
        self.week_files: list[Path] = []
        self.week_start: datetime = None
        self.week_end: datetime = None
        self.observations: list[str] = []
        self.updates: list[str] = []
        self.prunes: list[str] = []

    # ============================================================
    # 入口
    # ============================================================

    def run(self) -> dict:
        """主流程"""
        self._log("FridayDream 开始")

        # 1. Orient
        self._orient()
        # 2. Gather
        self._gather()
        # 3. Consolidate
        consolidated = self._consolidate()
        # 4. Prune
        self._prune()

        summary = self._build_summary()

        # 发送飞书通知
        self._notify(summary)

        self._log(f"FridayDream 完成: {summary['changes']}")
        return summary

    # ============================================================
    # Phase 1: Orient - 了解现有记忆结构
    # ============================================================

    def _orient(self):
        """读取现有 MEMORY.md，了解已有哪些主题"""
        self._log("Phase 1: Orient")

        if not os.path.exists(MEMORY_FILE):
            self._log("  MEMORY.md 不存在，跳过 Orient")
            return

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # 提取已有主题（## 标题）
        sections = re.findall(r"^##?\s+(.+)$", content, re.MULTILINE)
        self._log(f"  现有主题: {len(sections)} 个")
        for s in sections[:10]:
            self._log(f"    - {s}")

    # ============================================================
    # Phase 2: Gather - 收集本周信号
    # ============================================================

    def _gather(self):
        """扫描本周所有 memory 文件，收集值得记忆的内容"""
        self._log("Phase 2: Gather")

        # 计算本周范围（周一到周五）
        today = datetime.now()
        weekday = today.weekday()  # 0=Mon ... 4=Fri
        self.week_end = today
        self.week_start = today - timedelta(days=weekday)
        # 如果周五还没到收盘，用上周五
        if today.weekday() != 4 or today.hour < 15:
            # 取上周五
            days_since_friday = (today.weekday() - 4) % 7 + 7
            self.week_end = today - timedelta(days=(today.weekday() - 4 + 7) % 7 if today.weekday() >= 4 else 0)
            self.week_end = today - timedelta(days=days_since_friday)
            self.week_start = self.week_end - timedelta(days=4)

        self._log(f"  本周范围: {self.week_start.date()} ~ {self.week_end.date()}")

        # 扫描本周的 memory 文件
        self.week_files = self._find_week_files()

        if not self.week_files:
            self._log("  本周无 memory 文件")
            return

        self._log(f"  找到 {len(self.week_files)} 个文件")

        # 从每个文件提取关键信息
        signals = []
        for fpath in self.week_files:
            content = self._read_file(fpath)
            # 提取决策、盈亏、策略关键词
            decisions = self._extract_decisions(content)
            signals.extend(decisions)

        self._log(f"  提取到 {len(signals)} 条信号")

        # 从 portfolio.json 提取本周变化
        portfolio_changes = self._extract_portfolio_changes()
        if portfolio_changes:
            signals.extend(portfolio_changes)
            self._log(f"  持仓变化: {portfolio_changes}")

        # 从大盘数据提取表现
        market_perf = self._extract_market_performance()
        if market_perf:
            signals.append(market_perf)

        self.observations = signals

    def _find_week_files(self) -> list[Path]:
        """找本周的 memory 文件"""
        files = []
        mem_dir = Path(MEMORY_DIR)
        if not mem_dir.exists():
            return files

        for fpath in mem_dir.glob("*.md"):
            try:
                # 从文件名解析日期
                date_str = fpath.stem  # "2026-04-03"
                fdate = datetime.strptime(date_str, "%Y-%m-%d")
                if self.week_start <= fdate <= self.week_end:
                    files.append(fpath)
            except ValueError:
                continue

        # 也扫描子目录
        for subdir in mem_dir.iterdir():
            if subdir.is_dir():
                for fpath in subdir.rglob("*.md"):
                    try:
                        date_str = fpath.stem
                        fdate = datetime.strptime(date_str, "%Y-%m-%d")
                        if self.week_start <= fdate <= self.week_end:
                            files.append(fpath)
                    except ValueError:
                        continue

        return sorted(files)

    def _read_file(self, fpath: Path) -> str:
        """安全读取文件内容"""
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _extract_decisions(self, content: str) -> list[str]:
        """
        从 memory 内容中提取决策相关句子
        关键词模式：
        """
        decisions = []

        # 买入/卖出记录
        buy_matches = re.findall(r"[\u4e00-\u9fa5]*\u4e70[\u4e00-\u9fa5].{0,50}", content)
        sell_matches = re.findall(r"[\u4e00-\u9fa5]*\u5356[\u4e00-\u9fa5].{0,50}", content)
        for m in buy_matches[:5]:
            if len(m) > 5:
                decisions.append(f"买: {m.strip()}")
        for m in sell_matches[:5]:
            if len(m) > 5:
                decisions.append(f"卖: {m.strip()}")

        # 盈亏记录
        pnl_matches = re.findall(r"盈亏[^\n]{0,30}", content)
        for m in pnl_matches[:5]:
            decisions.append(m.strip())

        # 策略调整
        strategy_matches = re.findall(r"策略[^\n]{0,50}", content)
        for m in strategy_matches[:5]:
            decisions.append(m.strip())

        # 风控触发
        risk_matches = re.findall(r"止损|预警|风控[^\n]{0,30}", content)
        for m in risk_matches[:5]:
            decisions.append(m.strip())

        return decisions[:10]  # 最多10条

    def _extract_portfolio_changes(self) -> list[str]:
        """从 portfolio.json 提权本周持仓变化"""
        changes = []
        try:
            with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                portfolio = json.load(f)

            # 检查是否有 adjustment 记录
            adj = portfolio.get("meta", {}).get("adjustment", {})
            if adj:
                sold = adj.get("sold", [])
                bought = adj.get("bought", [])
                for s in sold:
                    changes.append(f"卖出: {s.get('name')} @ {s.get('price')} pnl={s.get('pnl')}")
                for b in bought:
                    changes.append(f"买入: {b.get('name')} @ {b.get('price')}")

            # 当前持仓状态
            mv = portfolio.get("market_value", {})
            pnl = portfolio.get("pnl", {})
            changes.append(f"周五收盘: 市值={mv.get('total', 0):,.0f} 总盈亏={pnl.get('total_pnl', 0):+,.0f}")

        except Exception as e:
            self._log(f"  portfolio.json 读取失败: {e}")

        return changes

    def _extract_market_performance(self) -> Optional[str]:
        """提取大盘本周表现"""
        try:
            with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                portfolio = json.load(f)

            indices = portfolio.get("indices", {})
            if not indices:
                return None

            lines = []
            for sym, info in indices.items():
                chg = info.get("chg_pct", 0)
                name = info.get("name", sym)
                lines.append(f"{name} {chg:+.2f}%")

            return "大盘: " + " | ".join(lines)
        except:
            return None

    # ============================================================
    # Phase 3: Consolidate - 整合到 MEMORY.md
    # ============================================================

    def _consolidate(self) -> dict:
        """将本周信号整合写入 MEMORY.md"""
        self._log("Phase 3: Consolidate")

        if not self.observations and not self.week_files:
            self._log("  无新内容需要整合")
            return {"changes": 0, "action": "skip"}

        # 构建本周总结
        week_summary = self._build_week_summary()

        # 读取当前 MEMORY.md
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = ""

        # 追加本周更新 section
        week_str = self.week_end.strftime("%Y-%m-%d")
        new_section = f"\n\n---\n\n## 本周整合 ({week_str})\n\n{week_summary}\n"

        # 找到最后一个分隔线或文件末尾
        if "## " in content:
            # 插入到 ## 标题之前
            last_section = content.rfind("## ")
            if last_section > 0:
                content = content[:last_section] + new_section + "\n" + content[last_section:]
            else:
                content = content + new_section
        else:
            content = content + new_section

        # 写回
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write(content)

        changes = len(self.observations)
        self._log(f"  写入 {changes} 条更新到 MEMORY.md")

        return {
            "changes": changes,
            "week_start": self.week_start.strftime("%Y-%m-%d"),
            "week_end": self.week_end.strftime("%Y-%m-%d"),
            "observations": self.observations[:5],
        }

    def _build_week_summary(self) -> str:
        """构建本周总结文本"""
        lines = []

        if self.observations:
            lines.append("**本周重要事件：**")
            for obs in self.observations[:8]:
                lines.append(f"- {obs}")
            lines.append("")

        # 持仓总结
        try:
            with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                p = json.load(f)
            pnl = p.get("pnl", {})
            mv = p.get("market_value", {})
            lines.append(f"**周五收盘：**")
            lines.append(f"- 总市值: {mv.get('total', 0):,.0f}")
            lines.append(f"- 总盈亏: {pnl.get('total_pnl', 0):+,.0f} ({pnl.get('total_pnl_pct', 0):+.2f}%)")
            lines.append(f"- 模型A: {pnl.get('model_a_pnl', 0):+,.0f} ({pnl.get('model_a_pnl_pct', 0):+.2f}%)")
            lines.append(f"- 模型B: {pnl.get('model_b_pnl', 0):+,.0f} ({pnl.get('model_b_pnl_pct', 0):+.2f}%)")
        except:
            pass

        # 策略有效性评估（简单启发式）
        if self.observations:
            buys = [o for o in self.observations if "买" in o]
            sells = [o for o in self.observations if "卖" in o]
            if buys:
                lines.append(f"**本周买入:** {len(buys)} 次")
            if sells:
                lines.append(f"**本周卖出:** {len(sells)} 次")

        return "\n".join(lines) if lines else "本周无显著更新。"

    # ============================================================
    # Phase 4: Prune - 精简 MEMORY.md
    # ============================================================

    def _prune(self):
        """保持 MEMORY.md 精简：检查是否超过阈值"""
        self._log("Phase 4: Prune")

        if not os.path.exists(MEMORY_FILE):
            return

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        size_kb = len(content.encode("utf-8")) / 1024

        if size_kb > 30:
            self._log(f"  MEMORY.md 大小 {size_kb:.1f}KB > 30KB，建议精简")
            self.prunes.append(f"文件过大({size_kb:.0f}KB)，建议清理")
        else:
            self._log(f"  MEMORY.md 大小 {size_kb:.1f}KB，在范围内")

        # 检查是否有模糊日期引用（使用严格的词边界匹配）
        fuzzy_patterns = [
            r"(?<![\u4e00-\u9fa5A-Za-z0-9])(?:今天|昨天|前天|大前天|明天|后天)(?![\u4e00-\u9fa5A-Za-z0-9])",
        ]
        weekday_cn = ["周一","周二","周三","周四","周五","周六","周日"]
        base_wday = self.week_end.weekday()
        for i, day in enumerate(weekday_cn):
            for prefix in ["本","这","上","下"]:
                if prefix == "下" and i == base_wday:
                    continue  # "下周一" from current day is same day
                escaped = re.escape(f"{prefix}{day}")
                fuzzy_patterns.append(
                    rf"(?<![\u4e00-\u9fa5A-Za-z0-9]){escaped}(?![\u4e00-\u9fa5A-Za-z0-9])"
                )

        fuzzy_found = []
        for pat in fuzzy_patterns:
            found = re.findall(pat, content)
            fuzzy_found.extend(found)

        if fuzzy_found:
            self._log(f"  发现模糊日期引用 {len(fuzzy_found)} 处: {set(fuzzy_found)}")
            self.prunes.append(f"MEMORY.md 存在模糊日期引用，应改为具体日期")

    # ============================================================
    # 辅助
    # ============================================================

    def _build_summary(self) -> dict:
        """构建最终摘要"""
        return {
            "date": self.week_end.strftime("%Y-%m-%d"),
            "files_reviewed": len(self.week_files),
            "observations": len(self.observations),
            "changes": self.updates,
            "prunes": self.prunes,
        }

    def _notify(self, summary: dict):
        """发送飞书通知"""
        if self.observations:
            lines = [
                f"🌙 FridayDream {summary['date']}",
                "=" * 28,
                f"本周memory文件: {summary['files_reviewed']} 个",
                f"提取信号: {summary['observations']} 条",
            ]
            if summary["changes"]:
                lines.append("")
                lines.append("**更新内容：**")
                for c in summary["changes"][:5]:
                    lines.append(f"  • {c}")
            if summary["prunes"]:
                lines.append("")
                lines.append("**建议清理：**")
                for p in summary["prunes"]:
                    lines.append(f"  • {p}")

            self.ctx.send_feishu("\n".join(lines))

    def _log(self, msg: str):
        """内部日志"""
        print(f"[FridayDream] {msg}")


# ============================================================
# 入口脚本
# ============================================================

if __name__ == "__main__":
    import uuid
    session_id = f"dream-{datetime.now().strftime('%Y%m%d')}"
    ctx = SkillContext(session_id=session_id)
    dream = FridayDream(ctx)
    result = dream.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
