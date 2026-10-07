import React from 'react'
import { QWEN_API_GUIDE_STEPS } from './qwenApiGuideSteps.js'

export default function QwenApiGuide() {
  const base = import.meta.env.BASE_URL
  return (
    <details className="qwen-api-guide">
      <summary>如何获取 API Key</summary>
      <div className="qwen-api-guide-content">
        <ol>
          {QWEN_API_GUIDE_STEPS.map(step => (
            <li key={step.number}>
              <h4><span>{step.number}</span>{step.title}</h4>
              <p>{step.description}</p>
              <a href={`${base}${step.image}`} target="_blank" rel="noreferrer" aria-label={`查看第 ${step.number} 步：${step.title}的大图`}>
                <img src={`${base}${step.image}`} alt={`操作${step.number}：${step.title}`} width={step.width} height={step.height} loading="lazy" decoding="async" />
              </a>
            </li>
          ))}
        </ol>
        <p className="qwen-api-guide-finish">复制后，先在百炼为所用模型开启“免费额度用完即停”，再到下方粘贴 Key、填写对应模型编号（默认 qwen-plus）、勾选确认项，点击“绑定个人 Key”。绑定本身不消耗模型额度。</p>
      </div>
    </details>
  )
}
