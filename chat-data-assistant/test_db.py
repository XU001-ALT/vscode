"""数据库连接测试脚本"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db import db_manager, get_table_list, execute_sql_safe


def main():
    print("=" * 50)
    print("数据库连接测试")
    print("=" * 50)

    # 1. 健康检查
    print("\n[1] 健康检查...")
    if db_manager.health_check():
        print("    ✅ 连接成功")
    else:
        print("    ❌ 连接失败，请检查 .env 配置")
        return

    # 2. 数据库信息
    print("\n[2] 数据库信息...")
    info = db_manager.get_info()
    print(f"    版本: {info['version']}")
    print(f"    数据库: {info['database']}")
    print(f"    用户: {info['user']}")

    # 3. 表列表
    print("\n[3] 表列表...")
    try:
        tables = get_table_list()
        if tables:
            for t in tables:
                print(f"    - {t}")
        else:
            print("    (无用户表)")
    except Exception as e:
        print(f"    获取表列表失败: {e}")

    # 4. 简单查询测试
    print("\n[4] 简单查询测试...")
    df, err = execute_sql_safe("SELECT 1 AS test_value")
    if df is not None:
        print(f"    ✅ 查询成功: {df.to_dict()}")
    else:
        print(f"    ❌ 查询失败: {err}")

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
