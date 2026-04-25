import React, { useState } from 'react';
import {
  HelpCircle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Copy,
  Check,
  AlertTriangle,
  Lightbulb,
  BookOpen,
  Zap,
  Shield,
  Server
} from 'lucide-react';

/**
 * API 配置教程组件
 * 为新手用户提供详细的 API 配置指导
 */
const ApiConfigGuide = () => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeSections, setActiveSections] = useState([]);
  const [copiedText, setCopiedText] = useState(null);

  // 复制到剪贴板
  const copyToClipboard = async (text, label) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedText(label);
      setTimeout(() => setCopiedText(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const toggleSection = (id) => {
    setActiveSections((previousSections) => {
      if (previousSections.includes(id)) {
        return previousSections.filter((sectionId) => sectionId !== id);
      }

      return [...previousSections, id];
    });
  };

  // 代码块组件
  const CodeBlock = ({ code, label }) => (
    <div className="relative group">
      <pre className="bg-gray-800 text-gray-100 rounded-lg p-3 text-sm overflow-x-auto font-mono">
        {code}
      </pre>
      <button
        type="button"
        onClick={() => copyToClipboard(code, label)}
        className="absolute top-2 right-2 p-1.5 bg-gray-700 hover:bg-gray-600 rounded opacity-0 group-hover:opacity-100 transition-opacity"
        title="复制"
      >
        {copiedText === label ? (
          <Check className="w-4 h-4 text-green-400" />
        ) : (
          <Copy className="w-4 h-4 text-gray-300" />
        )}
      </button>
    </div>
  );

  // 折叠区块组件
  const CollapsibleSection = ({ id, title, icon: Icon, children, badge }) => {
    const isActive = activeSections.includes(id);
    return (
      <div className="border border-gray-200 rounded-xl overflow-hidden">
        <button
          type="button"
          onClick={() => toggleSection(id)}
          className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center shadow-sm">
              <Icon className="w-4 h-4 text-blue-600" />
            </div>
            <span className="font-medium text-gray-800">{title}</span>
            {badge && (
              <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs font-medium rounded-full">
                {badge}
              </span>
            )}
          </div>
          {isActive ? (
            <ChevronUp className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          )}
        </button>
        {isActive && (
          <div className="p-4 bg-white border-t border-gray-100">
            {children}
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      data-api-guide-multi-expand="true"
      className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl shadow-ios overflow-hidden"
    >
      {/* 头部 - 可折叠 */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-6 hover:bg-white/50 transition-colors text-left"
      >
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
            <BookOpen className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              API 配置教程
              <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs font-medium rounded-full">
                新手必读
              </span>
            </h3>
            <p className="text-sm text-gray-500 mt-0.5">
              点击展开查看详细的 API 配置步骤和常见问题解答
            </p>
          </div>
        </div>
        <div className={`transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
          <ChevronDown className="w-6 h-6 text-gray-400" />
        </div>
      </button>

      {/* 展开内容 */}
      {isExpanded && (
        <div className="px-6 pb-6 space-y-4">
          {/* 快速概览 */}
          <div className="bg-white rounded-xl p-4 border border-blue-100">
            <div className="flex items-start gap-3">
              <Lightbulb className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-gray-800 mb-2">配置前须知</p>
                <ul className="text-sm text-gray-600 space-y-1.5">
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-1">•</span>
                    本系统使用 <strong>OpenAI 兼容格式</strong> 的 API，支持多种 AI 服务商
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-1">•</span>
                    推荐优先使用 <strong>gpt-5.5</strong>，需要控制成本时可选择 <strong>gpt-5.4</strong>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-500 mt-1">•</span>
                    您需要准备：API Key、Base URL、模型名称
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* 配置教程区块 */}
          <div className="space-y-3">
            {/* 第一步：获取 API */}
            <CollapsibleSection
              id="get-api"
              title="第一步：获取 API Key"
              icon={Shield}
              badge="必需"
            >
              <div className="space-y-4">
                <p className="text-sm text-gray-600">
                  您可以从以下服务商获取 API Key（选择一个即可）：
                </p>

                {/* Google AI Studio (Gemini) */}
                <div className="bg-gradient-to-r from-blue-50 to-green-50 rounded-lg p-4 border border-blue-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-800">Google AI Studio (Gemini)</span>
                    <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded">推荐</span>
                  </div>
                  <ol className="text-sm text-gray-600 space-y-2 mb-3">
                    <li>1. 访问 Google AI Studio</li>
                    <li>2. 使用 Google 账号登录</li>
                    <li>3. 点击 "Get API Key" 创建新的 API Key</li>
                    <li>4. 复制生成的 Key（格式如：AIzaSy...）</li>
                  </ol>
                  <a
                    href="https://aistudio.google.com/apikey"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium"
                  >
                    前往获取 <ExternalLink className="w-4 h-4" />
                  </a>
                </div>

                {/* OpenAI */}
                <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-800">OpenAI</span>
                  </div>
                  <ol className="text-sm text-gray-600 space-y-2 mb-3">
                    <li>1. 访问 OpenAI Platform</li>
                    <li>2. 注册/登录账号</li>
                    <li>3. 进入 API Keys 页面创建新 Key</li>
                    <li>4. 复制生成的 Key（格式如：sk-...）</li>
                  </ol>
                  <a
                    href="https://platform.openai.com/api-keys"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium"
                  >
                    前往获取 <ExternalLink className="w-4 h-4" />
                  </a>
                </div>

                {/* 第三方代理 */}
                <div className="bg-amber-50 rounded-lg p-4 border border-amber-200">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    <span className="font-medium text-gray-800">第三方 API 代理</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">
                    如果您使用 OneAPI、New API 等第三方代理服务，请从对应平台获取 API Key。
                    代理服务通常提供更低的价格和更多模型选择。
                  </p>
                  <p className="text-xs text-amber-700">
                    注意：使用第三方代理需确保其支持 OpenAI 兼容格式
                  </p>
                </div>
              </div>
            </CollapsibleSection>

            {/* 第二步：配置 Base URL */}
            <CollapsibleSection
              id="base-url"
              title="第二步：配置 Base URL"
              icon={Server}
              badge="必需"
            >
              <div className="space-y-4">
                <p className="text-sm text-gray-600">
                  Base URL 是 API 的访问地址，不同服务商的地址不同：
                </p>

                <div className="space-y-3">
                  {/* OpenAI 官方 */}
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-sm font-medium text-gray-700 mb-2">OpenAI 官方</p>
                    <CodeBlock code="https://api.openai.com/v1" label="openai-url" />
                  </div>

                  {/* Google Gemini (通过 OpenAI 兼容接口) */}
                  <div className="bg-blue-50 rounded-lg p-3">
                    <p className="text-sm font-medium text-gray-700 mb-2">
                      Google Gemini (OpenAI 兼容接口)
                    </p>
                    <CodeBlock code="https://generativelanguage.googleapis.com/v1beta/openai" label="gemini-url" />
                    <p className="text-xs text-gray-500 mt-2">
                      注：Google 官方提供的 OpenAI 兼容接口
                    </p>
                  </div>

                  {/* 第三方代理示例 */}
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-sm font-medium text-gray-700 mb-2">第三方代理（示例）</p>
                    <CodeBlock code="https://your-proxy-domain.com/v1" label="proxy-url" />
                    <p className="text-xs text-gray-500 mt-2">
                      请替换为您的代理服务地址，通常以 /v1 结尾
                    </p>
                  </div>

                  {/* 本地代理 */}
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-sm font-medium text-gray-700 mb-2">本地代理（如 OneAPI）</p>
                    <CodeBlock code="http://localhost:3000/v1" label="local-url" />
                  </div>
                </div>

                <div className="flex items-start gap-2 p-3 bg-amber-50 rounded-lg">
                  <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-amber-800">
                    <strong>重要：</strong>Base URL 必须以 <code className="bg-amber-100 px-1 rounded">/v1</code> 结尾，
                    且末尾不要有多余的斜杠 <code className="bg-amber-100 px-1 rounded">/</code>
                  </p>
                </div>
              </div>
            </CollapsibleSection>

            {/* 第三步：选择模型 */}
            <CollapsibleSection
              id="model"
              title="第三步：选择模型"
              icon={Zap}
            >
              <div className="space-y-4">
                <p className="text-sm text-gray-600">
                  根据您使用的 API 服务商，填写对应的模型名称：
                </p>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50">
                        <th className="text-left p-3 font-medium text-gray-700">服务商</th>
                        <th className="text-left p-3 font-medium text-gray-700">推荐模型</th>
                        <th className="text-left p-3 font-medium text-gray-700">特点</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      <tr className="bg-green-50/50">
                        <td className="p-3 text-gray-800">OpenAI</td>
                        <td className="p-3">
                          <code className="bg-green-100 text-green-800 px-2 py-0.5 rounded text-xs">
                            gpt-5.5
                          </code>
                        </td>
                        <td className="p-3 text-gray-600">旗舰模型，复杂任务效果好 ⭐</td>
                      </tr>
                      <tr>
                        <td className="p-3 text-gray-800">OpenAI</td>
                        <td className="p-3">
                          <code className="bg-gray-100 text-gray-800 px-2 py-0.5 rounded text-xs">
                            gpt-5.4
                          </code>
                        </td>
                        <td className="p-3 text-gray-600">通用能力强，成本更低</td>
                      </tr>
                      <tr>
                        <td className="p-3 text-gray-800">Google</td>
                        <td className="p-3">
                          <code className="bg-gray-100 text-gray-800 px-2 py-0.5 rounded text-xs">
                            gemini-3.1-pro-preview
                          </code>
                        </td>
                        <td className="p-3 text-gray-600">Gemini 3.1 Pro 预览版</td>
                      </tr>
                      <tr>
                        <td className="p-3 text-gray-800">Google</td>
                        <td className="p-3">
                          <code className="bg-gray-100 text-gray-800 px-2 py-0.5 rounded text-xs">
                            gemini-3-flash-preview
                          </code>
                        </td>
                        <td className="p-3 text-gray-600">速度快，适合日常任务</td>
                      </tr>
                      <tr>
                        <td className="p-3 text-gray-800">Claude</td>
                        <td className="p-3">
                          <code className="bg-gray-100 text-gray-800 px-2 py-0.5 rounded text-xs">
                            claude-opus-4-7
                          </code>
                        </td>
                        <td className="p-3 text-gray-600">长文写作和深度推理强</td>
                      </tr>
                      <tr>
                        <td className="p-3 text-gray-800">Claude</td>
                        <td className="p-3">
                          <code className="bg-gray-100 text-gray-800 px-2 py-0.5 rounded text-xs">
                            claude-sonnet-4-6
                          </code>
                        </td>
                        <td className="p-3 text-gray-600">写作能力优秀，响应更均衡</td>
                      </tr>
                      <tr>
                        <td className="p-3 text-gray-800">DeepSeek</td>
                        <td className="p-3">
                          <code className="bg-gray-100 text-gray-800 px-2 py-0.5 rounded text-xs">
                            deepseek-v4-pro
                          </code>
                        </td>
                        <td className="p-3 text-gray-600">中文理解好，复杂任务更稳</td>
                      </tr>
                      <tr>
                        <td className="p-3 text-gray-800">DeepSeek</td>
                        <td className="p-3">
                          <code className="bg-gray-100 text-gray-800 px-2 py-0.5 rounded text-xs">
                            deepseek-v4-flash
                          </code>
                        </td>
                        <td className="p-3 text-gray-600">速度快，价格更低</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div className="flex items-start gap-2 p-3 bg-blue-50 rounded-lg">
                  <Lightbulb className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-blue-800">
                    <strong>提示：</strong>如果使用第三方代理，请查看代理平台支持的模型列表，
                    并使用代理平台提供的模型名称（可能与官方略有不同）
                  </p>
                </div>
              </div>
            </CollapsibleSection>

            {/* 常见问题 */}
            <CollapsibleSection
              id="faq"
              title="常见问题排查"
              icon={HelpCircle}
            >
              <div className="space-y-4">
                {/* 问题 1 */}
                <div className="border-l-4 border-red-400 pl-4">
                  <p className="font-medium text-gray-800 mb-1">
                    错误：Your request was blocked
                  </p>
                  <p className="text-sm text-gray-600 mb-2">
                    这通常是因为 Gemini API 的内容安全策略触发。解决方法：
                  </p>
                  <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
                    <li>检查输入文本是否包含敏感内容</li>
                    <li>尝试简化或修改输入内容</li>
                    <li>如果频繁出现，考虑更换其他模型</li>
                  </ul>
                </div>

                {/* 问题 2 */}
                <div className="border-l-4 border-amber-400 pl-4">
                  <p className="font-medium text-gray-800 mb-1">
                    错误：API Key 无效或认证失败
                  </p>
                  <p className="text-sm text-gray-600 mb-2">
                    请检查以下几点：
                  </p>
                  <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
                    <li>确认 API Key 复制完整，没有多余空格</li>
                    <li>确认 API Key 没有过期或被禁用</li>
                    <li>确认 Base URL 与 API Key 匹配（同一服务商）</li>
                  </ul>
                </div>

                {/* 问题 3 */}
                <div className="border-l-4 border-blue-400 pl-4">
                  <p className="font-medium text-gray-800 mb-1">
                    错误：连接超时或网络错误
                  </p>
                  <p className="text-sm text-gray-600 mb-2">
                    可能的原因：
                  </p>
                  <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
                    <li>网络连接不稳定</li>
                    <li>Base URL 地址错误或无法访问</li>
                    <li>如果使用海外服务，可能需要代理</li>
                  </ul>
                </div>

                {/* 问题 4 */}
                <div className="border-l-4 border-purple-400 pl-4">
                  <p className="font-medium text-gray-800 mb-1">
                    错误：模型不存在或不支持
                  </p>
                  <p className="text-sm text-gray-600 mb-2">
                    请确认：
                  </p>
                  <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
                    <li>模型名称拼写正确</li>
                    <li>您的 API Key 有权限使用该模型</li>
                    <li>第三方代理是否支持该模型</li>
                  </ul>
                </div>
              </div>
            </CollapsibleSection>

            {/* 配置示例 */}
            <CollapsibleSection
              id="example"
              title="完整配置示例"
              icon={BookOpen}
            >
              <div className="space-y-4">
                <p className="text-sm text-gray-600">
                  以下是使用 OpenAI API 的完整配置示例：
                </p>

                <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                  <div>
                    <p className="text-xs text-gray-500 mb-1">模型名称</p>
                    <CodeBlock code="gpt-5.5" label="ex-model" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">API Key</p>
                    <CodeBlock code="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" label="ex-key" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Base URL</p>
                    <CodeBlock code="https://api.openai.com/v1" label="ex-url" />
                  </div>
                </div>

                <div className="flex items-start gap-2 p-3 bg-green-50 rounded-lg">
                  <Check className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-green-800">
                    配置完成后点击"保存配置"，配置会立即生效，无需重启服务！
                  </p>
                </div>
              </div>
            </CollapsibleSection>
          </div>

          {/* 底部提示 */}
          <div className="bg-white/80 rounded-xl p-4 text-center">
            <p className="text-sm text-gray-500">
              如有其他问题，请访问{' '}
              <a
                href="https://github.com/chi111i/GankAIGC/issues"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-700 font-medium"
              >
                GitHub Issues
              </a>
              {' '}提交反馈
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default ApiConfigGuide;
