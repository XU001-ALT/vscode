import type { Lang } from './types'

const dict = {
  // Header
  app_title: { zh: 'Chat Data for Digital Hydrogen', en: 'Chat Data for Digital Hydrogen' },
  lang_btn: { zh: 'English', en: '中文' },

  // Intro panel
  intro_area: { zh: 'Chat Data 介绍区', en: 'Chat Data Introduction' },
  intro_brand: { zh: 'Chat Data', en: 'Chat Data' },
  intro_p1_rest: {
    zh: ' 是一个面向智能数据分析的 AI 数据查询平台。通过自然语言与数据库交互，帮助用户更高效地探索、查询和分析数据。',
    en: ' is an AI-powered data query platform designed for intelligent data analysis. It connects users with databases through natural language interaction, helping users explore, query, and analyze data more efficiently.',
  },
  intro_p2: {
    zh: '平台结合数据库结构理解、智能查询生成与数据可视化，让用户无需编写复杂 SQL 即可完成从查询到分析的完整流程。',
    en: 'The platform combines database structure understanding, intelligent query generation, and data visualization, enabling users to complete the entire workflow from querying to analysis without writing complex SQL.',
  },
  intro_p3: {
    zh: '在「配置区」可以设置 API、查看数据库连接、管理 Schema，并通过「数据使用声明」了解各数据表的情况；在「对话绘图区」提交自然语言查询，即可获得数据结果与可视化分析。',
    en: "In the 'Config' panel you can manage API settings, check database connections, manage schema, and learn about each data table via the 'Data Usage Guide'. In the 'Chat & Plot' panel, submit natural-language queries to get results with visual analysis.",
  },
  intro_p4: {
    zh: '平台支持自然语言查询：在「对话绘图区」用一句话提问，AI 即可自动生成并执行 SQL 返回数据；并提供 12 种图表——折线图、柱状图、散点图、气泡散点、三维散点、相关性热力图、平行坐标、箱线分布、材料雷达图、饼图和直方图、面积图，可由 AI 自动推荐配置，也可手动切换调整；未配置 API Key 时可通过手动 SQL 直接绘图。',
    en: 'The platform supports natural-language querying: ask a question in the Chat & Plot panel and the AI automatically generates and executes SQL to return your data. Twelve chart types are available — line, bar, scatter, bubble, 3D scatter, correlation heatmap, parallel coordinates, box plot, material radar, pie, histogram, and area — with configs recommended by AI or adjustable manually. Without an API key you can still plot directly via manual SQL.',
  },
  intro_p5: {
    zh: 'AI 会自动分析你的提问意图：想画图时自动推荐合适的图表配置，想查数据时直接给出最大值、最小值、平均值等统计特例值，不适当或超出范围的问题会被提醒。',
    en: "The AI analyzes your intent automatically: chart requests get a suitable chart config recommended; data questions return quick statistics such as max, min, and average directly; inappropriate or out-of-scope questions receive a reminder.",
  },

  // Query panel
  chat_plot_area: { zh: '对话绘图区', en: 'Chat & Plot' },
  result_area: { zh: '结果展示区', en: 'Results' },
  query_ph: {
    zh: '请输入查询，例如：实验数据中的最高温度是多少？',
    en: 'Enter a query, e.g.: what is the maximum temperature in the experiments?',
  },
  send: { zh: '发送', en: 'Send' },
  querying: { zh: '查询中…', en: 'Querying…' },
  no_chart: { zh: '要渲染图表，请先执行查询得到数据。', en: 'Run a query first to render charts.' },
  result_tips: {
    zh: '在上方输入问题即可查询数据并生成图表。小提示：清晰具体的提问有助于 AI 准确理解你的意图——想绘图时可注明图表类型或关注的数据维度（如“用折线图展示温度随时间的变化”），只想查数据时直接描述所需内容；若图表未能按预期生成，通常是问法不够明确，换个更具体的说法再试即可。',
    en: "Type a question above to query data and generate charts. Tip: clear, specific questions help the AI understand your intent — for charts, mention the chart type or data dimensions (e.g. 'show temperature over time as a line chart'); for pure data questions, just describe what you need. If a chart isn't generated as expected, the question was likely ambiguous — try rephrasing it more specifically.",
  },
  rows_returned: { zh: '已返回 ', en: 'Returned ' },
  rows_unit: { zh: ' 行数据', en: ' rows' },
  use_ai_rec: { zh: '使用 AI 推荐的图表配置', en: 'Use AI-recommended chart config' },
  ai_reason: { zh: '推荐理由：', en: 'Reason: ' },
  chart_type_manual: { zh: '手动选择图型', en: 'Chart type' },
  line: { zh: '折线图', en: 'Line' },
  bar: { zh: '柱状图', en: 'Bar' },
  scatter: { zh: '散点图', en: 'Scatter' },
  pie: { zh: '饼图', en: 'Pie' },
  area: { zh: '面积图', en: 'Area' },
  histogram: { zh: '直方图', en: 'Histogram' },
  bubble: { zh: '气泡散点图', en: 'Bubble' },
  scatter3d: { zh: '三维散点图', en: '3D Scatter' },
  heatmap: { zh: '相关性热力图', en: 'Heatmap' },
  parallel: { zh: '平行坐标图', en: 'Parallel Coordinates' },
  box: { zh: '箱线分布图', en: 'Box Plot' },
  radar: { zh: '材料雷达图', en: 'Radar' },
  hist_y_axis: { zh: '频数', en: 'Count' },
  x_axis: { zh: 'X 轴', en: 'X axis' },
  y_axis_multi: { zh: 'Y 轴（可多选）', en: 'Y axis (multi)' },
  z_axis: { zh: 'Z 轴', en: 'Z axis' },
  size_field: { zh: '气泡大小', en: 'Bubble size' },
  color_field: { zh: '颜色', en: 'Color' },
  heatmap_hint: { zh: '自动使用全部数值列计算相关性矩阵', en: 'Auto-uses all numeric columns for the correlation matrix' },
  parallel_hint: { zh: '自动使用全部数值列对比多项指标', en: 'Auto-uses all numeric columns for multi-indicator comparison' },
  radar_hint: { zh: '自动使用全部数值列对比多指标（取前 N 条记录）', en: 'Auto-uses all numeric columns (top N records)' },
  category: { zh: '分类列', en: 'Category' },
  value: { zh: '数值列', en: 'Value' },
  filter_by: { zh: '按列筛选', en: 'Filter by' },
  filter_range: { zh: '范围筛选', en: 'Range filter' },
  filter_range_all: { zh: '全部', en: 'All' },
  filter_clear: { zh: '清除筛选', en: 'Clear filter' },
  no_numeric: { zh: '当前结果集中没有数值列可供绘图。', en: 'No numeric column available for plotting.' },
  no_numeric_pie: { zh: '饼图需要一个数值列作为占比。', en: 'Pie chart requires a numeric value column.' },
  reset: { zh: '重置', en: 'Reset' },
  data_table: { zh: '数据表', en: 'Table' },
  back_chart: { zh: '返回图表', en: 'Back to chart' },
  export_png: { zh: '导出 PNG', en: 'Export PNG' },
  manual_mode: { zh: '无 API Key · 手动绘图模式', en: 'No API key · Manual chart mode' },
  ai_mode: { zh: 'API Key 已配置 · AI 增强绘图模式', en: 'API key ready · AI-enhanced chart mode' },
  sql_input: { zh: 'SQL 查询（只读）', en: 'SQL query (read-only)' },
  sql_ph: { zh: '输入只读 SQL，例如：SELECT * FROM process LIMIT 100', en: 'Enter read-only SQL, e.g. SELECT * FROM process LIMIT 100' },
  run_sql: { zh: '执行查询', en: 'Run' },
  manual_hint: { zh: '当前未配置 API Key，使用手动绘图模式：直接填写 SQL 查询实时数据并绘图。', en: 'No API key configured. Manual mode: write SQL to query live data and plot.' },
  mode_ai_hint: { zh: '可使用自然语言生成查询与图表', en: 'Ask in natural language to generate SQL and charts' },
  mode_manual_hint: { zh: '可直接填写 SQL 手动绘图', en: 'Write SQL directly to plot manually' },
  view_sql: { zh: '查看生成 SQL', en: 'View SQL' },
  corrections: { zh: '自动修复记录', en: 'Auto-fix log' },
  no_corrections: { zh: '无修复记录（一次通过）', en: 'No fixes needed' },
  failed_sql: { zh: '失败 SQL：', en: 'Failed SQL: ' },
  fixed_sql: { zh: '修复为：', en: 'Fixed to: ' },
  manual_error_title: { zh: '手动查询出错', en: 'Manual query failed' },
  open_manual: { zh: '手动绘图', en: 'Manual plot' },
  close_manual: { zh: '收起手动绘图', en: 'Close manual plot' },
  manual_table: { zh: '选择数据表', en: 'Select table' },
  manual_table_ph: { zh: '请选择一张数据表', en: 'Choose a data table' },
  manual_cols: { zh: '列数', en: 'columns' },
  manual_loading: { zh: '正在加载数据…', en: 'Loading data…' },
  load_schema_first: {
    zh: '正在连接数据库并加载表结构，请稍候…',
    en: 'Connecting to the database and loading schema, please wait…',
  },
  querying_hint: {
    zh: 'AI 正在生成并执行 SQL，请稍候…',
    en: 'Generating and running SQL, please wait…',
  },

  // Error codes（后端 error_code → 双语文案；原始错误详情以小字附在下方）
  err_empty_question: { zh: '请输入查询内容。', en: 'Please enter a query.' },
  err_no_schema: {
    zh: '数据库表结构尚未就绪，系统正在初始化，请稍后重试。',
    en: 'Schema is not ready yet. The system is initializing, please try again shortly.',
  },
  err_db_unreachable: {
    zh: '数据库暂不可用，请稍后重试或联系管理员。',
    en: 'Database is unreachable. Try again later or contact the admin.',
  },
  err_llm_auth: {
    zh: 'API Key 无效或未配置，请在配置区检查。',
    en: 'API key is invalid or missing. Check the config panel.',
  },
  err_llm_timeout: {
    zh: 'LLM 请求超时，请稍后重试。',
    en: 'LLM request timed out. Please try again.',
  },
  err_llm_conn: {
    zh: '无法连接 LLM 服务，请检查网络与 Base URL。',
    en: 'Cannot reach the LLM service. Check network and Base URL.',
  },
  err_sql_failed: {
    zh: 'SQL 执行失败，可尝试换个问法。',
    en: 'SQL execution failed. Try rephrasing your question.',
  },
  err_no_valid_sql: {
    zh: '未能生成合法 SQL，请换个问法或确认问题在数据范围内。',
    en: 'Could not generate valid SQL. Rephrase or check the question scope.',
  },
  err_server_busy: {
    zh: '当前查询较多，系统繁忙，请稍后重试。',
    en: 'The system is busy with queries. Please try again shortly.',
  },
  err_unknown: { zh: '查询出错。', en: 'Query failed.' },

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
} as const

export type TKey = keyof typeof dict

export function t(key: TKey, lang: Lang): string {
  return dict[key][lang]
}
