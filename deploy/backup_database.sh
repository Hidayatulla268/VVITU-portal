#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# VVITU University Portal — Automated Daily Database Backup Script
# Place in cron: 0 2 * * * /var/www/vvitu/deploy/backup_database.sh
# ═══════════════════════════════════════════════════════════════════

BACKUP_DIR="/var/backups/vvitu"
DATE_TAG=$(date +"%Y-%m-%d_%H%M%S")
DB_NAME="vvitu_db"
DB_USER="vvitu_admin"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting PostgreSQL Backup for $DB_NAME..."
pg_dump -U "$DB_USER" -h localhost -Fc "$DB_NAME" > "$BACKUP_DIR/vvitu_db_${DATE_TAG}.dump"

# Keep last 30 days of backups, delete older
find "$BACKUP_DIR" -type f -name "*.dump" -mtime +30 -exec rm {} \;

echo "[$(date)] Backup completed successfully: $BACKUP_DIR/vvitu_db_${DATE_TAG}.dump"
