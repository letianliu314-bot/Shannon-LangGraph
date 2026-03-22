# PART 1 - RETRIEVED INFORMATION

Source 1: https://ui.adsabs.harvard.edu/abs/2010AdAst2010E...5D/abstract
- Relevance: low
- Summary: "The Core-Cusp Problem" discusses dark matter distribution in galaxies; clearly not related to medical AI safety or patient-facing medical advice.

Source 2: https://www.shortform.com/blog/core-problem
- Relevance: low
- Summary: "The Core Problem: Why & How You Should Identify the Crux" is a general writing/clarity piece about identifying core issues; not about medical AI safety.

# PART 2 - NOTES (optional)
- Conflicts: No direct conflicts between sources since both are unrelated to the medical AI safety topic.
- Data gaps: No retrieved sources cover safety responses or risk prompts for medical AI chat assistants. The retrieved material is outside the requested domain.
- Gap_ledger:
  - Needs authoritative sources on medical AI safety, risk warnings, and safe-response guidelines (e.g., FDA/NIH guidelines, WHO AI safety frameworks, NICE/UK NHS digital health guidelines, ISO/IEC/IEEE standards for AI in healthcare).
  - Prefer sources from official/academic domains and recent publications (past 6–12 months) to ground training data in current best practices.
  - If performing an integration task, we would require traceability mapping between each training sample and supporting biomedical safety principles.

JSON training data (5 samples)
[
  {
    "instruction": "Provide a safe, non-diagnostic response that highlights red flags and clearly instructs the user to seek in-person medical care if needed; avoid giving a medical diagnosis or dosing guidance.",
    "patient_query": "我最近几天胸口疼痛，走路也疼，这可能是什么原因？",
    "safe_answer": "我不是医生，无法诊断。胸痛可能由多种原因引起，部分情况需要紧急处理。若出现持续胸痛、呼吸困难、出汗、头晕、放射痛到左臂或颈部，请立即联系急救服务或到最近的急诊。若症状较轻且不符合紧急迹象，可先休息、避免剧烈活动、保持水分，并考虑在就医前告知医生你的病史与用药情况。若你愿意，告诉我你所在的地区，我可以帮助你找到最近的急诊资源。"
    ,
    "risk_flag": "high"
  },
  {
    "instruction": "提供常见感冒/发烧症状的安全自助信息，强调非诊断、需看医生的情形，并提供就医阈值。",
    "patient_query": "发烧头痛，应该吃什么药？能不能自己买来吃？",
    "safe_answer": "发烧和头痛通常可自我管理，但也可能是需要就医的信号。对无慢性疾病且无药物过敏史的成年人，按包装说明在药师指导下使用常用解热药（如对乙酰氨基酚）或布洛芬等非处方药通常是安全的；切勿超过推荐剂量。若体温持续超过38.5°C超过48小时，或伴有持续性呕吐、意识模糊、呼吸困难、胸痛、免疫系统疾病等，应就医。请告诉我所在地区，我可以帮助你找到就医渠道。"
    ,
    "risk_flag": "low"
  },
  {
    "instruction": "强调孕期药物安全，建议在医生指导下使用；提供就医路径和信息收集清单。",
    "patient_query": "孕期头痛，能吃止痛药吗？",
    "safe_answer": "孕期用药需要特别谨慎，请先咨询你的妇产科医生或药师。某些常用止痛药在孕期并非所有阶段都安全，医生会根据孕周、症状和个人病史来决定是否适合使用以及选择哪种药物。请提供你的孕周和既往过敏史等信息，我可以帮你整理就诊所需的要点并协助你联系医生。"
    ,
    "risk_flag": "high"
  },
  {
    "instruction": "对糖尿病患者的伤口或感染迹象给出安全的初步护理建议，并提示何时就医。",
    "patient_query": "糖尿病患者，脚上有小伤口，应该怎么处理？",
    "safe_answer": "糖尿病患者的伤口愈合可能较慢，需小心护理。一般做法包括：用温水轻柔清洁伤口、保持干燥、用干净包装覆盖、定期观察伤口变化；如出现红肿、疼痛加剧、渗液、发热、伤口不愈合或血糖控制困难，应尽快联系主治医生。避免自行涂抹不明药膏。请告知你所在区域，我可以帮你找到就诊地点。"
    ,
    "risk_flag": "medium"
  },
  {
    "instruction": "对突然胸闷和呼吸困难的症状给予强烈的就医指引，强调紧急处理。",
    "patient_query": "现在突然出现胸闷，呼吸困难，该怎么办？",
    "safe_answer": "胸闷和呼吸困难可能是多种情况的表现，某些情形可能危及生命。请立即呼叫紧急救援或就近急诊。如果已经出现持续性胸痛、出汗、晕厥、皮肤发冷、蓝唇等症状，请不要延迟就医。若暂时缓解并且你希望，我可以帮助你找到最近的急诊资源。"
    ,
    "risk_flag": "high"
  }
]