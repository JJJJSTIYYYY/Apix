const PptxGenJS = require("pptxgenjs");

// 创建PPT
const pptx = new PptxGenJS();

// 设置元数据
pptx.title = "原神社团招新";
pptx.subject = "原神社团2025年秋季招新";
pptx.author = "原神社团";

// ============================================
// 定义配色方案 - 原神星空冒险主题
// ============================================
const colors = {
  primary: "1A2F4B",      // 深蓝 - 夜空
  secondary: "D4A853",    // 金色 - 元素/冒险
  accent: "6B9AC4",       // 淡蓝 - 水元素
  light: "F5F1E6",        // 米白 - 云朵
  white: "FFFFFF",
  darkText: "2C3E50",
  goldDark: "B8934C"
};

// ============================================
// 定义字体 - 使用系统已安装的中文字体
// ============================================
const fonts = {
  title: "Noto Sans CJK SC",      // Noto Sans CJK SC用于标题
  body: "Noto Sans CJK SC",       // Noto Sans CJK SC用于正文
  boldTitle: "Noto Sans CJK SC"   // Noto Sans CJK SC用于加粗标题
};

// ============================================
// 定义通用样式
// ============================================

// 定义主标题样式
const mainTitleStyle = {
  fontSize: 44,
  fontFace: fonts.boldTitle,
  color: colors.secondary,
  bold: true,
  align: "center"
};

// 定义副标题样式
const subtitleStyle = {
  fontSize: 24,
  fontFace: fonts.body,
  color: colors.white,
  align: "center"
};

// 内容页标题样式
const contentTitleStyle = {
  fontSize: 36,
  fontFace: fonts.boldTitle,
  color: colors.primary,
  bold: true,
  align: "left"
};

// 正文样式
const bodyStyle = {
  fontSize: 18,
  fontFace: fonts.body,
  color: colors.darkText,
  align: "left"
};

// 小标题样式
const sectionHeaderStyle = {
  fontSize: 22,
  fontFace: fonts.title,
  color: colors.secondary,
  bold: true
};

// ============================================
// Slide 1: 封面
// ============================================
const slide1 = pptx.addSlide();
slide1.background = { color: colors.primary };

// 装饰性星星点缀（圆形代替）
for (let i = 0; i < 15; i++) {
  const x = Math.random() * 10;
  const y = Math.random() * 5.5;
  const size = 0.05 + Math.random() * 0.1;
  slide1.addShape(pptx.ShapeType.ellipse, {
    x: x, y: y, w: size, h: size,
    fill: { color: colors.secondary }
  });
}

// 主标题
slide1.addText("原神社团", {
  x: 0, y: 2, w: "100%", h: 1,
  ...mainTitleStyle,
  fontSize: 60,
  fontFace: fonts.boldTitle
});

// 副标题
slide1.addText("2025年秋季招新", {
  x: 0, y: 3, w: "100%", h: 0.8,
  ...subtitleStyle,
  fontFace: fonts.body
});

// 标语
slide1.addText("「 开启你的提瓦特冒险之旅 」", {
  x: 0, y: 3.8, w: "100%", h: 0.6,
  fontSize: 20,
  fontFace: fonts.body,
  color: colors.accent,
  align: "center",
  italic: true
});

// 装饰线条
slide1.addShape(pptx.ShapeType.line, {
  x: 3, y: 4.5, w: 4, h: 0,
  line: { color: colors.secondary, width: 2 }
});

// ============================================
// Slide 2: 关于我们
// ============================================
const slide2 = pptx.addSlide();
slide2.background = { color: colors.light };

// 页面标题
slide2.addText("关于我们", {
  x: 0.5, y: 0.4, w: 9, h: 0.8,
  ...contentTitleStyle,
  fontFace: fonts.boldTitle
});

// 左侧装饰块
slide2.addShape(pptx.ShapeType.rect, {
  x: 0.5, y: 1.4, w: 0.15, h: 3.5,
  fill: { color: colors.secondary }
});

// 社团简介
slide2.addText("原神社团是一个以《原神》游戏为主题的爱好者社群，汇聚了来自各学院的旅行者。", {
  x: 1, y: 1.5, w: 8, h: 0.8,
  ...bodyStyle,
  fontFace: fonts.body
});

// 核心数据 - 三个卡片
const stats = [
  { label: "社团成员", value: "200+", icon: "👥" },
  { label: "成立时间", value: "2021", icon: "📅" },
  { label: "活动场次", value: "50+", icon: "🎮" }
];

stats.forEach((stat, idx) => {
  const x = 0.8 + idx * 3;
  // 卡片背景
  slide2.addShape(pptx.ShapeType.roundRect, {
    x: x, y: 2.6, w: 2.5, h: 1.8,
    fill: { color: colors.white },
    line: { color: colors.accent, width: 1 },
    rectRadius: 0.1
  });
  // 数值
  slide2.addText(stat.value, {
    x: x, y: 2.8, w: 2.5, h: 0.8,
    fontSize: 36,
    fontFace: fonts.boldTitle,
    color: colors.secondary,
    bold: true,
    align: "center"
  });
  // 标签
  slide2.addText(stat.label, {
    x: x, y: 3.5, w: 2.5, h: 0.5,
    fontSize: 16,
    fontFace: fonts.body,
    color: colors.darkText,
    align: "center"
  });
});

// 社团宗旨
slide2.addShape(pptx.ShapeType.roundRect, {
  x: 0.8, y: 4.6, w: 8.4, h: 1,
  fill: { color: colors.primary }
});
slide2.addText("我们的宗旨：探索、分享、成长，一起在提瓦特大陆留下美好回忆", {
  x: 1, y: 4.8, w: 8, h: 0.6,
  fontSize: 16,
  fontFace: fonts.body,
  color: colors.white,
  align: "center"
});

// ============================================
// Slide 3: 社团活动
// ============================================
const slide3 = pptx.addSlide();
slide3.background = { color: colors.light };

// 页面标题
slide3.addText("社团活动", {
  x: 0.5, y: 0.4, w: 9, h: 0.8,
  ...contentTitleStyle,
  fontFace: fonts.boldTitle
});

// 活动列表 - 2x2网格布局
const activities = [
  { title: "联机副本挑战", desc: "每周组织深渊、周本联机活动" },
  { title: "版本讨论会", desc: "新版本前瞻直播、剧情分析" },
  { title: "COSPLAY展演", desc: "线下漫展、角色扮演活动" },
  { title: "同人创作", desc: "绘画、手书、小说创作分享" }
];

activities.forEach((act, idx) => {
  const col = idx % 2;
  const row = Math.floor(idx / 2);
  const x = 0.8 + col * 4.5;
  const y = 1.4 + row * 2.2;
  
  // 活动卡片
  slide3.addShape(pptx.ShapeType.roundRect, {
    x: x, y: y, w: 4, h: 1.9,
    fill: { color: colors.white },
    line: { color: colors.accent, width: 1.5 },
    rectRadius: 0.1
  });
  
  // 装饰色块
  slide3.addShape(pptx.ShapeType.rect, {
    x: x, y: y, w: 0.1, h: 1.9,
    fill: { color: colors.secondary }
  });
  
  // 活动标题
  slide3.addText(act.title, {
    x: x + 0.3, y: y + 0.3, w: 3.5, h: 0.5,
    fontSize: 20,
    fontFace: fonts.boldTitle,
    color: colors.primary,
    bold: true
  });
  
  // 活动描述
  slide3.addText(act.desc, {
    x: x + 0.3, y: y + 0.9, w: 3.5, h: 0.8,
    fontSize: 15,
    fontFace: fonts.body,
    color: colors.darkText
  });
});

// ============================================
// Slide 4: 部门介绍
// ============================================
const slide4 = pptx.addSlide();
slide4.background = { color: colors.light };

// 页面标题
slide4.addText("部门介绍", {
  x: 0.5, y: 0.4, w: 9, h: 0.8,
  ...contentTitleStyle,
  fontFace: fonts.boldTitle
});

// 部门列表
const departments = [
  { name: "组织部", desc: "策划组织各类社团活动", color: "E74C3C" },
  { name: "宣传部", desc: "运营社交媒体、制作宣传物料", color: "3498DB" },
  { name: "技术部", desc: "游戏攻略制作、数据分析", color: "27AE60" },
  { name: "外联部", desc: "与其他社团、厂商对接合作", color: "9B59B6" }
];

departments.forEach((dept, idx) => {
  const y = 1.4 + idx * 1.1;
  
  // 部门图标圆圈
  slide4.addShape(pptx.ShapeType.ellipse, {
    x: 0.8, y: y, w: 0.7, h: 0.7,
    fill: { color: dept.color }
  });
  
  // 部门名称
  slide4.addText(dept.name, {
    x: 1.8, y: y + 0.1, w: 2, h: 0.5,
    fontSize: 20,
    fontFace: fonts.boldTitle,
    color: colors.primary,
    bold: true
  });
  
  // 部门描述
  slide4.addText(dept.desc, {
    x: 4, y: y + 0.15, w: 5, h: 0.5,
    fontSize: 16,
    fontFace: fonts.body,
    color: colors.darkText
  });
  
  // 分隔线
  if (idx < departments.length - 1) {
    slide4.addShape(pptx.ShapeType.line, {
      x: 0.8, y: y + 0.9, w: 8.4, h: 0,
      line: { color: "D0D0D0", width: 1 }
    });
  }
});

// ============================================
// Slide 5: 招新信息
// ============================================
const slide5 = pptx.addSlide();
slide5.background = { color: colors.light };

// 页面标题
slide5.addText("招新信息", {
  x: 0.5, y: 0.4, w: 9, h: 0.8,
  ...contentTitleStyle,
  fontFace: fonts.boldTitle
});

// 左侧信息区
const infoItems = [
  { label: "招新对象", value: "全校在读学生（不限年级专业）" },
  { label: "报名时间", value: "即日起至9月30日" },
  { label: "面试时间", value: "10月5日-10月10日" },
  { label: "报名方式", value: "扫描二维码填写报名表" }
];

infoItems.forEach((item, idx) => {
  const y = 1.5 + idx * 1.1;
  
  // 标签
  slide5.addText(item.label + "：", {
    x: 0.8, y: y, w: 2, h: 0.5,
    fontSize: 18,
    fontFace: fonts.boldTitle,
    color: colors.secondary,
    bold: true
  });
  
  // 内容
  slide5.addText(item.value, {
    x: 3, y: y, w: 6, h: 0.5,
    fontSize: 18,
    fontFace: fonts.body,
    color: colors.darkText
  });
});

// 右侧装饰卡片
slide5.addShape(pptx.ShapeType.roundRect, {
  x: 6.5, y: 1.5, w: 3, h: 3.5,
  fill: { color: colors.primary },
  rectRadius: 0.2
});

slide5.addText("我们期待这样的你：", {
  x: 6.7, y: 1.8, w: 2.6, h: 0.5,
  fontSize: 16,
  fontFace: fonts.boldTitle,
  color: colors.secondary,
  bold: true,
  align: "center"
});

const qualities = ["热爱原神游戏", "有团队精神", "愿意学习成长", "有责任心"];
qualities.forEach((q, idx) => {
  slide5.addText("• " + q, {
    x: 6.7, y: 2.5 + idx * 0.5, w: 2.6, h: 0.4,
    fontSize: 14,
    fontFace: fonts.body,
    color: colors.light
  });
});

// ============================================
// Slide 6: 加入我们
// ============================================
const slide6 = pptx.addSlide();
slide6.background = { color: colors.primary };

// 标题
slide6.addText("加入我们", {
  x: 0, y: 0.8, w: "100%", h: 1,
  fontSize: 44,
  fontFace: fonts.boldTitle,
  color: colors.secondary,
  bold: true,
  align: "center"
});

// 副标题
slide6.addText("扫描下方二维码，开启你的社团之旅", {
  x: 0, y: 1.8, w: "100%", h: 0.6,
  fontSize: 18,
  fontFace: fonts.body,
  color: colors.light,
  align: "center"
});

// 模拟二维码区域（用形状代替）
slide6.addShape(pptx.ShapeType.roundRect, {
  x: 3.75, y: 2.6, w: 2.5, h: 2.5,
  fill: { color: colors.white },
  rectRadius: 0.1
});

// 二维码内部装饰
slide6.addText("QR CODE", {
  x: 3.75, y: 3.5, w: 2.5, h: 0.5,
  fontSize: 20,
  fontFace: fonts.boldTitle,
  color: colors.darkText,
  align: "center"
});

// 联系信息
slide6.addText("微信公众号：原神社团 | QQ群：123456789", {
  x: 0, y: 5.3, w: "100%", h: 0.4,
  fontSize: 14,
  fontFace: fonts.body,
  color: colors.accent,
  align: "center"
});

// ============================================
// Slide 7: 结尾页
// ============================================
const slide7 = pptx.addSlide();
slide7.background = { color: colors.primary };

// 装饰星星
for (let i = 0; i < 20; i++) {
  const x = Math.random() * 10;
  const y = Math.random() * 5.5;
  const size = 0.05 + Math.random() * 0.1;
  slide7.addShape(pptx.ShapeType.ellipse, {
    x: x, y: y, w: size, h: size,
    fill: { color: colors.secondary }
  });
}

// 主标语
slide7.addText("「 愿风神忽悠你 」", {
  x: 0, y: 2, w: "100%", h: 1,
  fontSize: 40,
  fontFace: fonts.boldTitle,
  color: colors.secondary,
  align: "center"
});

// 副标语
slide7.addText("期待在提瓦特大陆与你相遇", {
  x: 0, y: 3, w: "100%", h: 0.6,
  fontSize: 20,
  fontFace: fonts.body,
  color: colors.light,
  align: "center",
  italic: true
});

// 社团名称
slide7.addText("原神社团", {
  x: 0, y: 4, w: "100%", h: 0.6,
  fontSize: 24,
  fontFace: fonts.boldTitle,
  color: colors.accent,
  align: "center"
});

// 保存PPT
pptx.writeFile({ fileName: "原神社团招新PPT.pptx" })
  .then(() => {
    console.log("PPT创建成功！");
  })
  .catch((err) => {
    console.error("创建失败:", err);
  });

