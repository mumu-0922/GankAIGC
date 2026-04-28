#!/usr/bin/env python3
"""
数据库初始化和健康检查脚本
可以独立运行以测试数据库连接和初始化
"""

import sys
import os
from pathlib import Path

# 添加项目路径到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.database import init_db, engine, SessionLocal
from app.models.models import User, OptimizationSession, CustomPrompt, SystemSetting
from sqlalchemy import text, inspect


def check_database_connection():
    """检查数据库连接"""
    print("检查数据库连接...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        print("✓ 数据库连接成功")
        return True
    except Exception as e:
        print(f"✗ 数据库连接失败: {str(e)}")
        return False


def check_tables():
    """检查数据库表"""
    print("\n检查数据库表...")
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        expected_tables = [
            "users",
            "optimization_sessions",
            "optimization_segments",
            "session_history",
            "change_logs",
            "queue_status",
            "system_settings",
            "custom_prompts"
        ]
        
        missing_tables = [t for t in expected_tables if t not in tables]
        
        if missing_tables:
            print(f"⚠ 缺少以下表: {', '.join(missing_tables)}")
            return False
        else:
            print(f"✓ 所有必需的表都存在 ({len(expected_tables)} 个)")
            return True
    except Exception as e:
        print(f"✗ 检查表失败: {str(e)}")
        return False


def display_table_info():
    """显示表信息"""
    print("\n数据库表信息:")
    print("-" * 60)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        for table_name in sorted(tables):
            columns = inspector.get_columns(table_name)
            print(f"\n📊 {table_name} ({len(columns)} 列)")
            for col in columns[:5]:  # 只显示前5列
                col_type = str(col['type'])
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                print(f"   - {col['name']}: {col_type} {nullable}")
            if len(columns) > 5:
                print(f"   ... 还有 {len(columns) - 5} 列")
    except Exception as e:
        print(f"✗ 获取表信息失败: {str(e)}")


def check_data_integrity():
    """检查数据完整性"""
    print("\n检查数据完整性...")
    try:
        db = SessionLocal()
        try:
            # 检查用户数量
            user_count = db.query(User).count()
            print(f"✓ 用户数量: {user_count}")
            
            # 检查会话数量
            session_count = db.query(OptimizationSession).count()
            print(f"✓ 会话数量: {session_count}")
            
            # 检查系统提示词
            system_prompts = db.query(CustomPrompt).filter(CustomPrompt.is_system == True).count()
            print(f"✓ 系统提示词数量: {system_prompts}")
            
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"✗ 数据完整性检查失败: {str(e)}")
        return False


def test_crud_operations():
    """测试基本的 CRUD 操作"""
    print("\n测试数据库操作...")
    try:
        db = SessionLocal()
        try:
            # 测试创建
            test_setting = SystemSetting(
                key="test_key_delete_me",
                value="test_value"
            )
            db.add(test_setting)
            db.commit()
            print("✓ CREATE 操作成功")
            
            # 测试读取
            setting = db.query(SystemSetting).filter(
                SystemSetting.key == "test_key_delete_me"
            ).first()
            if setting:
                print("✓ READ 操作成功")
            
            # 测试更新
            setting.value = "updated_value"
            db.commit()
            print("✓ UPDATE 操作成功")
            
            # 测试删除
            db.delete(setting)
            db.commit()
            print("✓ DELETE 操作成功")
            
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"✗ CRUD 操作测试失败: {str(e)}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("数据库初始化和健康检查")
    print("=" * 60)
    
    # 检查环境变量
    env_file = backend_dir / ".env"
    if not env_file.exists():
        print(f"\n⚠ 警告: 未找到 .env 文件")
        print(f"   预期位置: {env_file}")
        print("   将使用默认配置\n")
    
    # 1. 检查数据库连接
    if not check_database_connection():
        print("\n❌ 数据库连接失败，无法继续")
        sys.exit(1)
    
    # 2. 初始化数据库
    print("\n" + "=" * 60)
    print("初始化数据库...")
    print("=" * 60)
    try:
        init_db()
    except Exception as e:
        print(f"\n❌ 数据库初始化失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # 3. 检查表
    if not check_tables():
        print("\n⚠ 警告: 某些表缺失")
    
    # 4. 显示表信息
    display_table_info()
    
    # 5. 检查数据完整性
    check_data_integrity()
    
    # 6. 测试 CRUD 操作
    test_crud_operations()
    
    # 总结
    print("\n" + "=" * 60)
    print("✓ 数据库检查完成!")
    print("=" * 60)
    print("\n数据库已就绪，可以启动应用")
    
    # 显示数据库类型
    from app.config import settings
    if settings.DATABASE_URL.startswith("postgresql"):
        print("\n📁 数据库: PostgreSQL")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ 用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
