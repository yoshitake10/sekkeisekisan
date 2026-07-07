let counter = 0

/** 一意なIDを生成する（プロジェクト保存を跨いでも衝突しにくい形式） */
export function genId(prefix = 'id'): string {
  counter = (counter + 1) % 1000
  return `${prefix}_${Date.now().toString(36)}${counter.toString(36)}${Math.random()
    .toString(36)
    .slice(2, 6)}`
}
