# 封面生成:信息来源说明 + 测试用例

> 覆盖三类业务:互动场景(workflow_scene)、代码实验室(lab / plaza 分享)、云课堂(cloud_course)。
> 代码入口:`src/app/api/routes/covers.py`、`src/app/api/routes/plaza.py`、
> `src/app/api/services/cover_engine.py`、`src/app/api/services/cover_sources.py`。

---

## 1. 封面生成到底拿到了什么信息

AI 文生图的 prompt 由 `cover_engine.py:39 build_prompt()` 统一拼接,**只用到两个字段**:

| 字段 | 用途 |
|------|------|
| `title` | 强制要求画在海报上的文字(Typography 部分) |
| `subtitle` | 作为 "Core Concept" 视觉隐喻来源;为空时回退用 `title` |

`biz_type` 参数传了但**未使用**——三类业务共用同一套 prompt 模板。
对话历史、代码内容、产物正文**均未参与** AI prompt。

### 各业务类型的 title / subtitle 来源

| 业务 | biz_type | title 来源 | subtitle 来源 | 是否优先直取产物 |
|------|----------|-----------|---------------|------------------|
| 云课堂 | `cloud_course` | generate:API body;regenerate:DB `cloud_courses.title` | generate:API body;regenerate:DB `description`(截断 2000 字) | 否,纯 AI 生成 |
| 互动场景 | `workflow_scene` | generate:API body(前端传场景标题);**regenerate:空串** | generate:API body;**regenerate:空** | 否,纯 AI 生成 |
| 互动讲义 | `interactive_lecture` | 同上(regenerate 同样为空) | 同上 | 否 |
| 代码实验室(分享) | `plaza_session_share` + content_type=`lab` | `_pick_share_title` 多级回退(见下) | `body.prompt_hint` > `share.description` | **是:GenUI `session.getCover` 设计图** |
| 讲义 PPT(分享) | 同上,content_type=`lecture` | 同上 | 同上 | **是:PPT 首页渲染** |
| 视频(分享) | 同上,content_type=`video` | 同上 | 同上 | **是:首个 `scene_*_static.png`** |

### Plaza 分享标题回退链(`plaza.py:598 _pick_share_title`)

```
请求 body.title
→ result_block.title
→ result_block.data.course_title / data.title
→ result_block.query(截 80 字)
→ agent_state.course_title / agent_state.title
→ environment_info.title / environment_info.name
→ "Untitled {content_type}"
```

### Prompt 实例

输入 `title="Python 数据分析入门"`,`subtitle="用 Pandas 完成数据清洗、聚合与可视化"`,实际发给文生图模型的 prompt(节选):

```
Act as a world-class graphic designer. Create a highly diverse, visually
breathtaking course cover poster. Crucial requirements:
1. Typography: You MUST write the exact text 'Python 数据分析入门' on the poster. ...
2. Core Concept: '用 Pandas 完成数据清洗、聚合与可视化'. Interpret this concept
   into a stunning visual metaphor.
3. Artistic Diversity & Vibe: ... 4. Subject-Specific Color Palette: ...
5. Composition: Masterful 16:9 widescreen composition ...
```

若 `subtitle` 为空,则 Core Concept 直接用 `title`。

---

## 2. 测试用例

### 2.1 互动场景(workflow_scene)

| 编号 | 用例 | 步骤 | 预期 |
|------|------|------|------|
| WS-01 | 正常生成 | `POST /covers/generate`,body:`{biz_type:"workflow_scene", biz_id:"<场景id>", title:"太阳系行星探索", subtitle:"拖拽行星观察轨道与公转周期变化"}` | 返回 `{job_id, cover_status:"pending"}`;轮询 status 变 `ready`;封面图上出现文字"太阳系行星探索",画面主题与轨道/行星相关 |
| WS-02 | subtitle 为空回退 | 同上但 `subtitle` 不传,`title:"垃圾分类小游戏"` | 正常生成;Core Concept 回退为 title,画面主题与垃圾分类相关 |
| WS-03 | 幂等/防重复 | WS-01 完成后,对同一 biz_id 再次调用 generate | 直接返回缓存:`cover_status:"ready"` + 原 `cover_url`,不创建新 job;若上一 job 仍 pending/generating 则返回原 job_id |
| WS-04 | 重新生成 | `POST /covers/regenerate`,body:`{biz_type:"workflow_scene", biz_id:"<同上>"}` | 创建新 job 并最终 ready。⚠️ 已知现状:regenerate 分支只对 cloud_course 回查 DB,workflow_scene 的 title/subtitle 为空串(`covers.py:342-357`),封面会失去标题文字——验证时确认该行为,评估是否需补场景标题回查 |
| WS-05 | 越权访问 | 用户 B 对用户 A 的场景调用 generate / regenerate | 403/404,不创建 job |
| WS-06 | 长标题与特殊字符 | `title` 传 80+ 字、含引号/emoji/换行 | 请求不报错;prompt 中 `{title!r}` 正确转义;图片仍能生成(文字可能被模型截断,记录实际表现) |

### 2.2 代码实验室(lab,plaza 分享)

| 编号 | 用例 | 步骤 | 预期 |
|------|------|------|------|
| LAB-01 | 发布即直取设计图 | GenUI session 存活时发布 lab 分享(`create_or_update_plaza_share`) | `_cache_cover_at_publish` 同步调 GenUI `session.getCover`,封面 = 已渲染设计图;**不创建** AI 生成 job;cover_biz_state 为 ready |
| LAB-02 | 直取失败回退 AI | GenUI session 已销毁/平台不可达后,调 `POST .../shares/{id}/cover`(generate_content_cover) | 直取返回 None → 创建 AI job;title 走回退链(block.title → agent_state…),subtitle = `share.description`;最终 ready,封面含标题文字 |
| LAB-03 | prompt_hint 覆盖 | 同 LAB-02,body 传 `prompt_hint:"赛博朋克风格的代码编辑器"` | subtitle 用 prompt_hint 而非 description;画面体现该风格 |
| LAB-04 | 标题回退链 | 构造分享:不传 body.title,result_block 无 title 但有 `query:"做一个贪吃蛇小游戏"` | 分享标题 = query 前 80 字;AI 封面文字为该 query 文本 |
| LAB-05 | 全部回退兜底 | 分享的 block/agent_state/environment_info 均无标题 | 标题 = `"Untitled lab"`;封面仍能生成(文字为 Untitled lab,记录是否可接受) |
| LAB-06 | 已有封面不重复 | LAB-01 完成后再调 generate_content_cover | 直接返回已 ready 的 cover_url,不再请求 GenUI 也不建 job |

### 2.3 云课堂(cloud_course)

| 编号 | 用例 | 步骤 | 预期 |
|------|------|------|------|
| CC-01 | 正常生成 | `POST /covers/generate`,body:`{biz_type:"cloud_course", biz_id:"<课程id>", title:"机器学习导论", subtitle:"从线性回归到神经网络的十周课程"}` | job ready;封面含文字"机器学习导论",主题贴合 subtitle |
| CC-02 | regenerate 回查 DB | 先在 DB 中给课程设置 title="高等数学(上)"、description="极限、导数与一元积分";调 `POST /covers/regenerate` | 不依赖 body,title/subtitle 取自 `cloud_courses` 表;description 超 2000 字时截断到 2000 |
| CC-03 | description 为空 | 课程无 description,调 regenerate | subtitle=None,Core Concept 回退为 title;正常生成 |
| CC-04 | 非属主 regenerate | 用户 B 对用户 A 的课程 regenerate | 403/404(`_require_biz_owner`) |
| CC-05 | 状态机与失败恢复 | 临时使 OPENROUTER key 失效后 generate | job 进入 error,cover_biz_state.coverStatus="error" 带 cover_error;恢复 key 后 regenerate 能重新成功 |
| CC-06 | 文件与状态一致性 | DB 中 state=ready 但手动删除 `uploads/covers/cloud_course/<id>.png` 后 generate | `covers.py:266` 检测文件不存在 → 不返回缓存,重新创建 job 生成 |

---

## 3. 验证要点速查

- 生成的封面文件落盘:`uploads/covers/{biz_type}/{biz_id}.png`(plaza 直取走 `_persist_direct_cover_png`)。
- 模型/比例由环境变量控制:`OPENROUTER_COVER_IMAGE_MODEL`、`OPENROUTER_COVER_IMAGE_ASPECT_RATIO`(默认 16:9)、`OPENROUTER_COVER_IMAGE_K`。
- 异步链路:`enqueue_cover_job` → `cover_worker.process_cover_job` → `generate_cover_png_bytes`;状态依次 pending → generating → ready/error。
- 已知差异点(测试时重点关注):
  1. `workflow_scene` / `interactive_lecture` 的 **regenerate 不回查标题**,生成的封面无主题信息(WS-04)。
  2. lab/lecture/video 分享发布瞬间直取产物,GenUI session 销毁后只能 AI 回退(LAB-02)。
  3. AI prompt 不区分 biz_type,三类业务封面风格策略一致。
