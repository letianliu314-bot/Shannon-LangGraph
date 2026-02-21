# Shannon-LangGraph

Shannon-LangGraph 是一个基于 LangGraph 的数据集生成/编排项目，分为编排层、LLM Service、存储层三大模块。

## 核心流程
1. 用户请求 -> 生成数据集 Spec
2. Spec -> 执行 Plan
3. Task Queue 调度 -> LLM/工具调用
4. 验证 -> 通过或容错处理
5. 打包输出（含缺口原因）

## 快速启动
```bash
make init
make install
make run-orchestration
make run-llm
```

## Workflow 模板（YAML）使用
已内置示例模板到 `config/workflows/examples/`，可通过编排层直接调用。

1. 列出模板
```bash
curl -s http://127.0.0.1:8000/workflows/templates
```

2. 查看模板详情（支持 `extends` 合并后结果）
```bash
curl -s http://127.0.0.1:8000/workflows/templates/market_analysis_playbook
```

3. 按模板运行
```bash
curl -s -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "wf-demo-1",
    "workflow_template": "parallel_items_example",
    "user_request": "生成本周技术快报",
    "workflow_context": {
      "topics": ["AI", "Cybersecurity", "Robotics"],
      "depth": "brief"
    }
  }'
```

## Web 调试前端
已提供一个可本地调试的 Next.js 前端，目录为 `desktop/`，用于查看 run 执行与事件流。

```bash
cd desktop
cp -n .env.example .env.local
# 需要本机安装 Node.js (含 npm)
npm install
npm run dev
```

浏览器打开 `http://localhost:3000`。

## 目录结构
见 `docs/architecture.md`。
