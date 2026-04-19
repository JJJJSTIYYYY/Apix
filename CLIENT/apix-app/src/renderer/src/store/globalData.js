export const apix_client_version = '2.0.1'

export const defaultCards = () => [
  { id: '-annotation-preset', title: '注释卡片', type: 'note', level: 'system' },
  { id: '-script-preset', title: '脚本卡片', type: 'script', level: 'system' },
  { id: '-folder-preset', title: '卡片夹', type: 'folder', level: 'system' },
  // { id: '-if-preset', title: '条件卡片', type: 'if', level: 'system' },
  // { id: '-loop-preset', title: '循环卡片', type: 'loop', level: 'system' },
  // { id: '-switch-preset', title: '分支卡片', type: 'switch', level: 'system' },
  { id: 'interface-preset', title: '接口请求', type: 'interface', level: 'system' },
  { id: 'database-preset', title: '数据库请求', type: 'database', level: 'system' },
]

export const globalState = {
  allowToInput: true, // 全局文本输入框disable标记
  draggedStartCardUid_parent: 0, // 记录被拖拽对象的来源，不是被拖拽对象的uid
  draggedStartCardUid: 0, // 记录被拖拽对象的uid
  draggedTabCard: "",
  draggedCard: ""
};

export function clearDragMark() {
  globalState.draggedStartCardUid_parent = 0 // 记录被拖拽对象的来源，不是被拖拽对象的uid
  globalState.draggedStartCardUid = 0 // 记录被拖拽对象的uid
  globalState.draggedTabCard = ""
  globalState.draggedCard = ""
}

/**
 * 将字符串转为字典对象，支持类型推断
 * @param {string} rawString
 * @returns {Record<string, any> | { error: string }}
 */
export function StringToDict(rawString) {
  if (typeof rawString !== "string") {
    return { error: "Input must be a string" }
  }

  const dict = {}

  const parseValue = (val) => {
    const trimmed = val.trim()

    // boolean
    if (/^(true|false)$/i.test(trimmed)) {
      return trimmed.toLowerCase() === "true"
    }

    // number
    if (!isNaN(trimmed) && trimmed !== "") {
      return Number(trimmed)
    }

    // array (用 JSON.parse 尝试)
    if (/^\[.*\]$/.test(trimmed)) {
      try {
        return JSON.parse(trimmed)
      } catch {
        return trimmed // 解析失败就当字符串
      }
    }

    // object/dict (允许 key 不加引号)
    if (/^\{.*\}$/.test(trimmed)) {
      try {
        // 把 {a:1, b:"2"} 这种，转换成 {"a":1,"b":"2"} 再解析
        const fixed = trimmed
          .replace(/([{,]\s*)([a-zA-Z_][\w]*)\s*:/g, '$1"$2":')
        return JSON.parse(fixed)
      } catch {
        return trimmed
      }
    }

    // 默认当 string
    return trimmed
  }

  try {
    const lines = rawString.split("\n")

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith("#")) continue // 跳过空行和注释

      const [key, ...rest] = trimmed.split(":")
      if (!key || rest.length === 0) {
        return { error: `Invalid line format: "${line}"` }
      }

      const cleanKey = key.trim()
      const value = rest.join(":") // 防止值里有冒号
      dict[cleanKey] = parseValue(value)
    }

    return dict
  } catch (e) {
    return { error: "Failed to parse string" }
  }
}



/**
 * 将字符串数组转换成 [{label, value}, ...] 格式
 * @param {string[]} list 
 * @returns {{label: string, value: string}[]}
 */
export function formatVarNameList(list) {
  return list.map(item => ({
    label: item,
    value: item
  }));
}
