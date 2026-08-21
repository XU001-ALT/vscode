import type { Lang } from './types'

const dict = {
  // Header
  app_title: { zh: 'Chat Data for Digital Hydrogen', en: 'Chat Data for Digital Hydrogen' },
  lang_btn: { zh: 'English', en: '中文' },

  // Intro panel
  intro_title: { zh: '介绍', en: 'Introduction' },
  intro_p1: {
    zh: 'Chat Data 是一个面向智能数据分析的 AI 数据查询平台。通过自然语言与数据库交互，帮助用户更高效地探索、查询和分析数据。',
    en: 'Chat Data is an AI-powered data query platform designed for intelligent data analysis. It connects users with databases through natural language interaction, helping users explore, query, and analyze data more efficiently.',
  },
  intro_p2: {
    zh: '平台结合数据库结构理解、智能查询生成与数据可视化，让用户无需编写复杂 SQL 即可完成从查询到分析的完整流程。',
    en: 'The platform combines database structure understanding, intelligent query generation, and data visualization, enabling users to complete the entire workflow from querying to analysis without writing complex SQL.',
  },
  intro_p3: {
    zh: '在「配置区」可以设置 API、查看数据库连接并管理 Schema；在「对话绘图区」提交自然语言查询，即可获得数据结果与可视化分析。',
    en: "In the 'Config' panel you can manage API settings, database connections and schema. In the 'Chat & Plot' panel, submit natural-language queries to get results with visual analysis.",
  },

  // Query panel
  chat_plot_area: { zh: '对话绘图区', en: 'Chat & Plot' },
  query_ph: {
    zh: '请输入查询，例如：查看所有实验数据中温度大于500的记录',
    en: 'Enter a query, e.g.: show all records where temperature > 500',
  },
  send: { zh: '发送', en: 'Send' },
  querying: { zh: '查询中…', en: 'Querying…' },
  tab_data: { zh: '数据预览', en: 'Data Preview' },
  tab_chart: { zh: '图表', en: 'Chart' },
  export_csv: { zh: '导出 CSV', en: 'Export CSV' },
  no_result: { zh: '目前没有查询结果，发送查询以生成数据。', en: 'No results yet. Send a query to generate data.' },
  no_chart: { zh: '要渲染图表，请先执行查询得到数据。', en: 'Run a query first to render charts.' },
  rows_returned: { zh: '已返回 ', en: 'Returned ' },
  rows_unit: { zh: ' 行数据', en: ' rows' },
  use_ai_rec: { zh: '使用 AI 推荐的图表配置', en: 'Use AI-recommended chart config' },
  ai_reason: { zh: '推荐理由：', en: 'Reason: ' },
  chart_type_manual: { zh: '手动选择图型', en: 'Chart type' },
  line: { zh: '折线图', en: 'Line' },
  bar: { zh: '柱状图', en: 'Bar' },
  scatter: { zh: '散点图', en: 'Scatter' },
  pie: { zh: '饼图', en: 'Pie' },
  x_axis: { zh: 'X 轴', en: 'X axis' },
  y_axis_multi: { zh: 'Y 轴（可多选）', en: 'Y axis (multi)' },
  category: { zh: '分类列', en: 'Category' },
  value: { zh: '数值列', en: 'Value' },
  no_numeric: { zh: '当前结果集中没有数值列可供绘图。', en: 'No numeric column available for plotting.' },
  no_numeric_pie: { zh: '饼图需要一个数值列作为占比。', en: 'Pie chart requires a numeric value column.' },
  load_schema_first: {
    zh: '请先在右侧配置区加载 Schema（从数据库拉取或上传）。',
    en: "Load a schema first in the config panel (fetch from database or upload).",
  },

  // Config panel
  config_area: { zh: '配置区', en: 'Configuration' },
  db_status: { zh: '数据库连接', en: 'Database Connection' },
  db_connected: { zh: '数据库已连接', en: 'Database connected' },
  db_connecting: { zh: '正在连接数据库…', en: 'Connecting to database…' },
  db_failed: { zh: '数据库连接失败', en: 'Database connection failed' },
  api_config: { zh: 'API 配置', en: 'API Configuration' },
  api_config_hint: {
    zh: '填写后使用你自己的大模型，费用由你承担；留空则使用系统默认配置。',
    en: 'Fill in to use your own LLM (costs on you); leave empty for system default.',
  },
  model_select: { zh: '模型预设', en: 'Model Preset' },
  custom: { zh: '自定义…', en: 'Custom…' },
  base_url: { zh: 'API Base URL', en: 'API Base URL' },
  api_key: { zh: 'API Key', en: 'API Key' },
  key_set: { zh: '已设置', en: 'Set' },
  current_key: { zh: '当前密钥', en: 'Current key' },
  clear: { zh: '清除', en: 'Clear' },
  model_name: { zh: '模型名称', en: 'Model Name' },
  model_name_ph: { zh: '留空自动选择（如 deepseek-v4-flash / gpt-4o-mini）', en: 'Leave empty for auto-select (e.g. deepseek-v4-flash / gpt-4o-mini)' },
  save: { zh: '保存', en: 'Save' },
  saved: { zh: '已保存', en: 'Saved' },
  data_guide: { zh: '数据使用声明', en: 'Data Usage Guide' },
  data_guide_body: {
    zh: '本平台仅对数据库执行只读查询（SELECT）。AI 生成的 SQL 会经过安全校验，禁止任何修改数据的操作。查询结果仅用于当前会话的可视化分析。',
    en: 'This platform only executes read-only queries (SELECT) against the database. AI-generated SQL passes security validation; any data-modifying operation is rejected. Query results are used only for visualization in the current session.',
  },
  schema_mgmt: { zh: 'Schema 管理', en: 'Schema Management' },
  fetch_schema: { zh: '从数据库拉取 Schema', en: 'Fetch Schema from Database' },
  fetching: { zh: '正在拉取表结构…', en: 'Fetching table structures…' },
  upload_schema: { zh: '上传 Schema 文件', en: 'Upload Schema File' },
  upload_hint: { zh: '支持 Python ORM / JSON / TXT', en: 'Python ORM / JSON / TXT supported' },
  loaded_tables: { zh: '已加载表：', en: 'Loaded tables: ' },
  schema_err: { zh: 'Schema 处理失败：', en: 'Schema failed: ' },
} as const

export type TKey = keyof typeof dict

export function t(key: TKey, lang: Lang): string {
  return dict[key][lang]
}
