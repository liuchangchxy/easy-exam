/* ==========================================================================
   EasyExam 产品原型 · 共享界面词典（第四轮）
   --------------------------------------------------------------------------
   只覆盖「产品外壳」：侧栏导航、分组标签、品牌副题、顶栏控件、底导、
   账户菜单与面包屑入口。题库正文、解析与数据驱动的列表内容保持原始语言
   （与设置页「界面语言」的说明一致：内容不随界面语言翻译）。

   页面里带 data-i18n="shell.*" 的元素由 spec-boot 的外壳接线统一替换；
   设置页自带更完整的词典，键名不同，互不影响。
   ========================================================================== */
window.eeI18N = {
  'shell.group.learn': ['学习', 'Study'],
  'shell.brand.sub': ['私人学习档案', 'Private study archive'],
  'shell.nav.today': ['今天', 'Today'],
  'shell.nav.banks': ['题库', 'Banks'],
  'shell.nav.review': ['复习', 'Review'],
  'shell.nav.exams': ['模考', 'Exams'],
  'shell.nav.notes': ['资料', 'Materials'],
  'shell.nav.settings': ['设置', 'Settings'],
  'shell.nav.more': ['更多', 'More'],
  'shell.crumb.study': ['学习', 'Study'],
  'shell.tb.search': ['搜索与跳转', 'Search and jump'],
  'shell.tb.search.q': ['搜索题库', 'Search banks'],
  'shell.tb.theme.toDark': ['切换到深色', 'Switch to dark'],
  'shell.tb.theme.toLight': ['切换到浅色', 'Switch to light'],
  'shell.tb.theme.toggle': ['切换明暗', 'Toggle light or dark'],
  'shell.tb.lang': ['切换语言', 'Switch language'],
  'shell.tb.account': ['账户菜单', 'Account menu'],
  'shell.menu.profile': ['账户资料', 'Account'],
  'shell.menu.settings': ['设置', 'Settings'],
  'shell.menu.instance': ['实例管理', 'Instance admin'],
  'shell.menu.logout': ['退出登录', 'Sign out'],
  'shell.cmd.title': ['搜索与跳转', 'Search and jump'],
  'shell.cmd.placeholder': ['搜索页面，或输入名称跳转', 'Search pages, or type a name to jump'],
  'shell.cmd.empty': ['没有匹配的页面', 'No matching page'],
  'shell.cmd.foot': ['↑↓ 选择 · Enter 打开 · Esc 关闭', '↑↓ select · Enter open · Esc close'],
  'shell.signout.title': ['退出登录', 'Sign out'],
  'shell.signout.desc': ['退出后回到登录页；这台设备上的学习记录仍保留在实例里。', 'You will return to the sign-in page. Your study history stays in the instance.'],
  'shell.signout.ok': ['退出登录', 'Sign out'],
  'shell.signout.cancel': ['取消', 'Cancel']
};
