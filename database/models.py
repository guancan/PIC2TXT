"""
数据库模型定义
定义任务表、结果表、数据源表和笔记任务关联表的结构
"""

# 任务状态常量
TASK_STATUS_PENDING = 'pending'      # 等待处理
TASK_STATUS_PROCESSING = 'processing'  # 处理中
TASK_STATUS_COMPLETED = 'completed'   # 已完成
TASK_STATUS_FAILED = 'failed'        # 失败

# OCR引擎类型常量
OCR_ENGINE_LOCAL = 'local'           # 本地PaddleOCR
OCR_ENGINE_MISTRAL = 'mistral'       # Mistral AI OCR
OCR_ENGINE_NLP = 'nlp'               # 新增自然语言分析引擎类型

# 创建任务表的SQL语句
CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT,                         -- 图片/PDF的URL
    file_path TEXT,                   -- 本地文件路径
    status TEXT,                      -- 状态：pending, processing, completed, failed
    ocr_engine TEXT DEFAULT 'local',  -- OCR引擎类型：local, mistral, nlp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 更新时间
    error_message TEXT                -- 错误信息（如果有）
);
"""

# 创建结果表的SQL语句
CREATE_RESULTS_TABLE = """
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,                  -- 关联的任务ID
    text_content TEXT,                -- OCR识别的文本内容
    result_path TEXT,                 -- 结果文件路径
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    FOREIGN KEY (task_id) REFERENCES tasks (id)
);
"""

# 创建数据源表的SQL语句
CREATE_DATA_SOURCES_TABLE = """
CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT,                 -- 数据源类型：csv, database, api
    source_path TEXT,                 -- 数据源路径或连接字符串
    config TEXT,                      -- 数据源配置（JSON格式）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- 更新时间
);
"""

# 创建笔记任务关联表的SQL语句
CREATE_NOTE_TASK_RELATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS note_task_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_url TEXT UNIQUE,             -- 笔记URL（作为唯一标识）
    task_ids TEXT,                    -- 关联的任务ID列表（JSON格式）
    status TEXT,                      -- 状态：pending, processing, completed, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- 更新时间
);
"""
