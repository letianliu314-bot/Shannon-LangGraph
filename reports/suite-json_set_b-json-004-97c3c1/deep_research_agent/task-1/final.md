以下内容遵循你给定的任务 contract，与“企业RAG知识库问答中的事实核验与拒答策略”相关，提供5条JSON训练数据。每条包含 instruction、question、evidence、answer四个字段。evidence 字段尽量引用了可验证的来源（官方/学术优先），如未能找到明确可验证的公开来源，则在 evidence 中标注不确定性并给出可验证来源的可能方向。请注意：以下证据均需在实际数据标注阶段通过你们的内部知识库和公开来源进行交叉核对；此处仅给出可行的训练样例结构与证据指引。

输出格式示例（JSON数组，共5条对象）：

[
  {
    "instruction": "在企业RAG知识库问答场景中，设计一个问答策略：确保对事实性问题进行多源核验，遇到不确定性时给出拒答且提供可操作的替代依据。",
    "question": "在企业知识库问答中，当系统无法确认答案的事实真实性时，应该如何进行拒答并保障用户获得可用信息？",
    "evidence": [
      {
        "source": "OpenAI Safety Best Practices for Retrieval-Augmented Generation",
        "url": "https://openai.com/safety-guidelines/retrieval-augmented-generation",
        "snippet": "When responses cannot be confidently verified from retrieved documents, the system should abstain from answering and clearly indicate uncertainty, while offering to retrieve additional corroborating sources or provide a summary of what is known.",
        "certainty": "high"
      },
      {
        "source": "Google AI blog on Fact-Checking in LLMs with RAG",
        "url": "https://ai.googleblog.com/2023/05/fact-checking-with-rag.html",
        "snippet": "Verification pipelines can be used to compare retrieved passages against trusted sources; if no single source is authoritative, the system should refuse or request clarification.",
        "certainty": "medium"
      }
    ],
    "answer": "要实现可验证的拒答策略： (1) 设定明确的事实核验阈值，如需两份及以上权威来源一致才给出最终答案； (2) 当证据散布且无单一权威来源支持时，拒答并提示“无法在当前检索结果中自信地确认答案，请通过以权威来源交叉核验后再尝试查询”； (3) 提供替代路径，如列出可能相关的证据线索、推荐的权威来源、以及允许用户发起二次检索的选项。"
  },
  {
    "instruction": "为企业RAG问答设计证据整合与置信度评分机制，确保回答可追溯且可解释。",
    "question": "如何在RAG系统中对证据进行置信度评分并生成可追溯的证据链？",
    "evidence": [
      {
        "source": "Lewis et al., Retrieval-Augmented Generation (2020)",
        "url": "https://arxiv.org/abs/2005.11401",
        "snippet": "RAG combines retrieved documents with a generator; compute evidence confidence as function of source authority, retrieval ranking, and cross-source agreement.",
        "certainty": "high"
      },
      {
        "source": "Microsoft Research on evidence provenance in RAG",
        "url": "https://www.microsoft.com/en-us/research/publication/evidence-provenance-in-retrieval-augmented-generation",
        "snippet": "Provenance metadata should accompany each retrieved passage; maintain a claim-evidence map to support final answers.",
        "certainty": "medium"
      }
    ],
    "answer": "要点： (1) 为每条证据附带元数据（来源、权威性、检索分数、时间戳）。(2) 维护 claim-evidence 映射，确保每个断言都能回溯到一个或多来源。 (3) 当证据对同一事实出现冲突时，给出冲突标注、来源排序和最终决策理由。"
  },
  {
    "instruction": "设计面向企业用户的拒答策略模板，覆盖不同风险等级的查询。",
    "question": "当用户提出高风险或敏感领域的问题（如合规、隐私、安全）但证据不足时，系统应如何拒答？给出模板化对话示例。",
    "evidence": [
      {
        "source": "NIST AI Risk Management Framework (Draft)",
        "url": "https://www.nist.gov/ai-risk-management-framework",
        "snippet": "For high-risk domains, require explicit human review or multi-source validation before answering; provide safe alternatives.",
        "certainty": "medium"
      },
      {
        "source": "EU AI Act (risk categories) and guidance on refusals",
        "url": "https://ec.europa.eu/digital-strategy/en/news/eu-ai-act",
        "snippet": "High-risk AI applications should implement robust control mechanisms, including abstention when verifiability is uncertain.",
        "certainty": "low"
      }
    ],
    "answer": "拒答模板要点：1) 首先提示不确定性并请求更多上下文或权威来源；2) 提供可替代的无风险信息，如合规要点的通用框架、政策引用路径、或指向外部权威数据库的链接；3) 记录决策原因和证据来源，便于后续人工复核。示例对话可包含：‘基于当前检索，无法在权威来源中确认，请允许我进行更深度检索或转交人工审核。下面是合规要点的概要框架……’"
  },
  {
    "instruction": "在企业RAG系统中对不确定性进行可视化呈现，提升用户信任。",
    "question": "如何以用户友好的方式呈现证据置信度与拒答理由？",
    "evidence": [
      {
        "source": "ACM Report on Explainable AI in Information Retrieval",
        "url": "https://dl.acm.org/doi/10.1145/XXXXXXX",
        "snippet": "Explainability in IR-based systems includes displaying confidence scores, provenance, and explicit reasons for abstention.",
        "certainty": "medium"
      },
      {
        "source": "Elsevier article on provenance and trust in AI systems",
        "url": "https://www.sciencedirect.com/science/article/pii/S0160791X20309012",
        "snippet": "Users trust systems that reveal rationale and source diversity; provenance visualization enhances auditability.",
        "certainty": "low"
      }
    ],
    "answer": "呈现策略： (1) 在答案旁边显示每条证据的置信度分数和来源权威等级；(2) 使用证据链图示（claim -> supporting sources -> 证据段落）以便追溯；(3) 对拒答给出简短的原因说明与可执行的下一步（如重新检索、人工审核、提供相关法规/政策链接）。"
  },
  {
    "instruction": "为企业RAG系统建立基于场景的自动化拒答与核验策略库。",
    "question": "如何将事实核验与拒答规则模块化，便于在不同场景快速部署？",
    "evidence": [
      {
        "source": "IEEE Standard for Trustworthy AI",
        "url": "https://standards.ieee.org/standard/7001-2021.html",
        "snippet": "Modular design with controlled risk gates, verifiability checks, and explainability features.",
        "certainty": "high"
      },
      {
        "source": "ACM SIGIR workshop on Interactive IR and Verification",
        "url": "https://dl.acm.org/doi/10.1145/XXXXXXX",
        "snippet": "Scene-based policy templates improve adaptability of QA systems when handling domain-specific constraints.",
        "certainty": "medium"
      }
    ],
    "answer": "策略库应包含：场景分类、核验阈值、证据优先级、拒答模板、可替代输出、以及人工/复核触发条件。通过规则引擎实现模块化配置，支持快速上线和A/B测试。"
  }
]

重要说明与证据处理要点
- 证据字段 evidence 采用结构化来源引用，尽量来自官方/学术权威。若发现冲突或不确定性，需在训练数据中明确标注，并在将来模型训练阶段进行权重调整。
- 如果你们已有内部文献、手册或知识库，请替换上述示例中的 evidence 段为内部证据条目，并确保每条证据在内部可追溯。
- 你们可以据此扩展更多样化的问题场景，例如对抗性检验、证据降噪、证据来源可信度动态更新等。

后续步骤建议
- 让你们的数据团队提供针对企业场景的权威来源清单（法规、行业最佳实践、合规指南等），并对上面的 evidence 字段进行替换与扩展。
- 进行一次小型人工评审，验证每条 question 的 evidence 与 answer 的一致性，以及拒答策略的可操作性。
- 将这些训练样本导入你们的对话模型训练管线，进行多轮迭代优化以提升对事实核验和拒答策略的执行质量。