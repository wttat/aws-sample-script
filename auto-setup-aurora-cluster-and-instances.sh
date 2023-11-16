#!/bin/bash

set -e

# 使用 AWS STS 获取当前 IAM 实体信息，并直接打印到屏幕
echo "获取当前 IAM 实体信息..."
aws sts get-caller-identity | cat

# 检查是否提供了快照标识符和集群标识符
if [ "$#" -ne 2 ]; then
    echo "用法: $0 <快照标识符> <集群标识符>"
    exit 1
fi

SNAPSHOT_IDENTIFIER=$1
CLUSTER_IDENTIFIER=$2
INSTANCE_SIZE="db.r5.large"  # 实例大小设置为 db.r5.large
INSTANCE_IDENTIFIER="instance-in-${CLUSTER_IDENTIFIER}"

# 从快照恢复Aurora集群
echo "正在从快照 $SNAPSHOT_IDENTIFIER 恢复 Aurora 集群 $CLUSTER_IDENTIFIER..."
aws rds restore-db-cluster-from-snapshot \
    --snapshot-identifier $SNAPSHOT_IDENTIFIER \
    --db-cluster-identifier $CLUSTER_IDENTIFIER \
    --engine aurora-postgresql | cat

# 检查集群状态
echo "正在等待集群 $CLUSTER_IDENTIFIER 变为可用状态..."
aws rds wait db-cluster-available --db-cluster-identifier $CLUSTER_IDENTIFIER

# 集群创建完毕后，在集群内创建Aurora实例
echo "正在集群 $CLUSTER_IDENTIFIER 中创建 Aurora 实例 $INSTANCE_IDENTIFIER..."
aws rds create-db-instance \
    --db-instance-identifier $INSTANCE_IDENTIFIER \
    --db-instance-class $INSTANCE_SIZE \
    --db-cluster-identifier $CLUSTER_IDENTIFIER \
    --engine aurora-postgresql | cat

# 监控Aurora实例的创建过程
echo "正在监控 Aurora 实例 $INSTANCE_IDENTIFIER 的创建过程..."
aws rds wait db-instance-available --db-instance-identifier $INSTANCE_IDENTIFIER

echo "Aurora 实例 $INSTANCE_IDENTIFIER 创建完成。"
