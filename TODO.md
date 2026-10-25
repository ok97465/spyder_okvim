# Neovim 사용성 개선 TO-DO

번호는 중요도가 아니라 **각 항목의 전체 범위를 구현하고 관련 동작을 확인하는 데 필요한 상대 작업량**을 뜻한다. 같은 규모 안의 순서는 추정이며, 실제 일정이나 코드 줄 수를 보장하지 않는다. `보완-XX`, `추가-XX`는 최초 제안 목록의 번호다.

규모는 `매우 작음 → 작음 → 중간 → 큼 → 매우 큼`으로 구분한다. 기존 함수의 국소 수정에서 시작해, 여러 모드·창·비동기 처리에 걸친 구조 변경으로 갈수록 규모를 크게 잡았다.

보완 중 반응 시간에 영향을 미치는 사항에 대해서는 진행 여부를 사용자에게 문의한다.

- [ ] **05. 재들여쓰기 연산자 `=` 추가** — 추가-07 · 중간

  작업: `==`, `={motion}`, `gg=G`를 현재 문서의 재들여쓰기 기능에 연결한다. 전체 포맷과 재들여쓰기의 적용 범위를 구분한다.

  완료 기준: 현재 줄·지정 범위·전체 문서에 적용되며, 문서 설정과 undo 단위를 유지한다. 선행 권장: 02.

  관련 코드: [executor_normal.py](spyder_okvim/executor/executor_normal.py), [executor_sub.py](spyder_okvim/executor/executor_sub.py), [action_helpers.py](spyder_okvim/utils/action_helpers.py).

- [ ] **06. 삽입·줄 추가 명령의 횟수 처리** — 보완-03 · 중간

  작업: `i`, `a`, `A`, `o`, `O`의 count를 삽입 종료 시 반영하고, `.` 반복과 연결한다.

  완료 기준: `80i-<Esc>`와 `3oabc<Esc>` 등이 입력 횟수를 반영하며, 취소·다시 실행·undo 시 입력이 중복되거나 누락되지 않는다.

  관련 코드: [executor_normal.py](spyder_okvim/executor/executor_normal.py), [status.py](spyder_okvim/vim/status.py), [vim_widgets.py](spyder_okvim/spyder/vim_widgets.py).

- [ ] **07. 검색 시 멈춤 방지와 결과 갱신** — 보완-01 · 중간

  작업: 길이 0인 정규식 일치에서도 검색 위치를 전진시키고, 문서 편집·파일 전환 시 일치 목록을 갱신한다.

  완료 기준: `^`, `$`, 단어 경계 검색이 종료되며, 편집으로 추가·삭제된 일치를 `n/N`과 강조 표시에 반영한다. 다른 문서의 결과를 재사용하지 않는다.

  관련 코드: [search_helpers.py](spyder_okvim/utils/search_helpers.py), [search.py](spyder_okvim/vim/search.py), [status.py](spyder_okvim/vim/status.py).

- [ ] **08. 레지스터의 표준 동작 완성** — 보완-04 · 중간

  작업: 대문자 이름의 추가 저장, 이름 지정 yank/delete의 무명 레지스터 갱신, 삭제 이력 `"1`~`"9`를 구현한다.

  완료 기준: `"Ayy`가 `a`에 덧붙고, 이름 지정 복사·삭제 후 기본 붙여넣기가 일관되며, 기존 `"0`·`"+`·블랙홀 사용 흐름을 유지한다.

  관련 코드: [status.py](spyder_okvim/vim/status.py), [action_helpers.py](spyder_okvim/utils/action_helpers.py).

- [ ] **09. 검색·명령 입력에서 한글 IME 지원** — 보완-10 · 중간

  작업: `/`·`:` 입력 중에는 한글 조합을 허용하고, 입력 완료·취소 후 Normal 명령 처리로 복귀하도록 한다. 기존 Insert 편집기의 IME 동작을 유지한다.

  완료 기준: 한글 검색어의 조합·수정·Enter·Esc가 정상 동작하고, 이후 Normal 명령이 오작동하지 않는다. 실제 운영체제의 IME로 확인한다.

  관련 코드: [vim_widgets.py](spyder_okvim/spyder/vim_widgets.py), [executor_sub.py](spyder_okvim/executor/executor_sub.py), [executor_colon.py](spyder_okvim/executor/executor_colon.py).

- [ ] **10. 역방향·증분 검색 추가** — 추가-05 · 중간

  작업: `?pattern`, 입력 중 일치 미리보기, 빈 검색의 이전 패턴 재사용, 검색 방향에 따른 `n/N`을 구현한다.

  완료 기준: `/`와 `?`의 방향을 기억하고, Esc로 증분 검색을 취소하면 시작 위치·선택을 복원한다. 선행 권장: 07.

  관련 코드: [executor_sub.py](spyder_okvim/executor/executor_sub.py), [mixins.py](spyder_okvim/executor/mixins.py), [search_helpers.py](spyder_okvim/utils/search_helpers.py), [search.py](spyder_okvim/vim/search.py).

- [ ] **11. 명령줄·검색 이력과 자동완성 추가** — 추가-06 · 중간

  작업: Ex 명령과 검색어의 이력을 분리해 위·아래 키로 조회하고, Tab으로 지원 명령·파일 경로를 완성한다.

  완료 기준: 입력 중인 내용을 잃지 않고 이력을 왕복하며, 검색 입력에서는 Ex 완성이 개입하지 않는다. 한글 경로와 공백이 있는 경로도 처리한다.

  관련 코드: [vim_widgets.py](spyder_okvim/spyder/vim_widgets.py), [executor_colon.py](spyder_okvim/executor/executor_colon.py), [executor_sub.py](spyder_okvim/executor/executor_sub.py).

- [ ] **12. 매크로의 재실행·추가 녹화·중단 보완** — 보완-05 · 큼

  작업: `@@`, 기존 `a`에 이어 녹화하는 `qA`, 재생 중 중단과 종료 시 정리를 구현한다.

  완료 기준: 반복 재생·추가 녹화가 일관되며, 중단 후 대기 중인 이벤트가 편집을 계속하지 않는다. 파일 전환·창 닫기 후에도 녹화 연결과 작업자가 남지 않는다.

  관련 코드: [macro.py](spyder_okvim/vim/macro.py), [executor_normal.py](spyder_okvim/executor/executor_normal.py), [executor_sub.py](spyder_okvim/executor/executor_sub.py), [vim_widgets.py](spyder_okvim/spyder/vim_widgets.py).

- [ ] **13. 파일 탐색기의 결과 정확성과 응답성 보완** — 보완-09 · 큼

  작업: 빈 결과에서 이전 목록을 제거하고, 확장자·제외 경로 설정, 현재 파일 폴더 기준 탐색, 백그라운드 파일 수집과 캐시를 지원한다.

  완료 기준: 결과가 0개일 때 관련 없는 파일이 열리지 않으며, 프로젝트가 없는 경우에도 탐색할 수 있다. 대규모 폴더 수집 중 입력·취소가 가능하다.

  관련 코드: [file_search.py](spyder_okvim/utils/file_search.py), [vim_widgets.py](spyder_okvim/spyder/vim_widgets.py), [config.py](spyder_okvim/spyder/config.py), [confpage.py](spyder_okvim/spyder/confpage.py).

- [ ] **14. 범위 지정 치환 `:s` 추가** — 추가-01 · 큼

  작업: Ex 범위 파서와 치환 실행기를 추가해 `%`, 줄 번호 범위, Visual 범위 및 `g/c` 플래그를 지원한다.

  완료 기준: `:%s/foo/bar/gc`, `:10,20s/foo/bar/g`, `:'<,'>s/foo/bar/g`가 지정 범위에만 적용된다. 치환 확인·취소와 undo도 일관되게 처리한다. 선행 권장: 07.

  관련 코드: [executor_colon.py](spyder_okvim/executor/executor_colon.py), [executor_visual.py](spyder_okvim/executor/executor_visual.py), [executor_vline.py](spyder_okvim/executor/executor_vline.py), [action_helpers.py](spyder_okvim/utils/action_helpers.py).

- [ ] **15. 파일·버퍼·분할창의 표준 명령 추가** — 추가-09 · 큼

  작업: `:e 경로`, `:bnext`, `:bprevious`, `Ctrl+^`, `:split`, `:vsplit`, `Ctrl+w h/j/k/l`을 Spyder 편집기 기능에 연결한다.

  완료 기준: 파일 열기·버퍼 전환·분할·창 이동 후 대상 편집기에 명령이 적용되며, 기존 `gt/gT`와 점프 목록을 유지한다. 창 문맥 처리는 18과 함께 정리한다.

  관련 코드: [executor_colon.py](spyder_okvim/executor/executor_colon.py), [executor_sub.py](spyder_okvim/executor/executor_sub.py), [vim_widgets.py](spyder_okvim/spyder/vim_widgets.py), [cursor.py](spyder_okvim/vim/cursor.py).

- [ ] **16. 모드별 사용자 키 매핑 추가** — 추가-04 · 큼

  작업: Normal·Insert·Visual별 매핑 설정, 여러 키로 구성된 매핑, 접두키 대기와 충돌 처리, 표준 키 설정 묶음을 제공한다. 기존 leader·Leap 설정을 반영한다.

  완료 기준: `jk` 등의 사용자 매핑이 지정 모드에서만 동작하며, 매핑과 원래 명령의 접두키가 겹쳐도 입력을 잃지 않는다. Spyder 단축키와의 우선순위를 설정할 수 있다.

  관련 코드: [vim_widgets.py](spyder_okvim/spyder/vim_widgets.py), [config.py](spyder_okvim/spyder/config.py), [confpage.py](spyder_okvim/spyder/confpage.py), [executor_base.py](spyder_okvim/executor/executor_base.py), [plugin.py](spyder_okvim/spyder/plugin.py).

- [ ] **17. 프로젝트 본문 검색과 Quickfix 결과 탐색 추가** — 추가-10 · 매우 큼

  작업: Spyder의 전체 검색 기능과 연결해 파일·줄·열 정보를 갖는 결과 목록을 만들고, `:cnext`·`:cprevious` 등으로 순회한다.

  완료 기준: 여러 파일의 검색 결과로 정확히 이동하며, 검색 중 취소·결과 갱신·점프 목록을 지원한다. 파일명 검색과 독립된 본문 검색 흐름을 제공한다.

  관련 코드: [executor_colon.py](spyder_okvim/executor/executor_colon.py), [executor_leader.py](spyder_okvim/executor/executor_leader.py), [list_dialog.py](spyder_okvim/utils/list_dialog.py), [jump_list.py](spyder_okvim/utils/jump_list.py). 검색 결과 모델과 연동 코드는 새로 추가한다.

- [ ] **18. 포커스 이동과 분리 편집창의 모드 유지 보완** — 보완-06 · 매우 큼

  작업: 메인 명령 입력창의 포커스에 묶인 모드 전환을 정리하고, 각 편집창·분리창에 입력 처리와 활성 편집기 문맥을 연결한다.

  완료 기준: 콘솔·검색창·탭·분리창을 왕복해도 의도한 모드와 선택을 유지한다. 각 창에서 Esc가 동작하며 닫힌 창의 연결을 정리한다.

  관련 코드: [plugin.py](spyder_okvim/spyder/plugin.py), [vim_widgets.py](spyder_okvim/spyder/vim_widgets.py), [status.py](spyder_okvim/vim/status.py), [cursor.py](spyder_okvim/vim/cursor.py).

- [ ] **19. Insert·Replace 모드의 Vim 편집 명령 추가** — 추가-08 · 매우 큼

  작업: 연속 덮어쓰기 `R`, 삽입 중 레지스터 입력 `Ctrl+r`, Normal 명령 한 번 실행 후 복귀하는 `Ctrl+o`, `Ctrl+[` 복귀를 구현한다.

  완료 기준: 자동완성·IME와 함께 동작하고, Replace 상태의 입력·수정·종료 및 `.`·매크로·undo가 일관된다. 선행 권장: 01, 06, 08. 입력 처리 구조는 16·18과 공유한다.

  관련 코드: [state.py](spyder_okvim/vim/state.py), [status.py](spyder_okvim/vim/status.py), [executor_normal.py](spyder_okvim/executor/executor_normal.py), [vim_widgets.py](spyder_okvim/spyder/vim_widgets.py). Insert·Replace 입력 처리 계층을 추가한다.

- [ ] **20. Visual Block과 직전 선택 복원 `gv` 추가** — 추가-02 · 매우 큼

  작업: 직사각형 선택 상태·표시와 열 단위 `I/A/c/d/y/p`를 구현하고, 이전 Visual 영역·모드를 저장해 `gv`로 복원한다.

  완료 기준: 길이가 다른 줄과 탭이 포함된 줄에서 열 선택·편집·붙여넣기가 동작한다. `gv`, `.` 반복, 레지스터, undo를 일관되게 처리한다. 선행 권장: 01, 08. 입력과 선택 문맥은 18·19와 함께 확인한다.

  관련 코드: [state.py](spyder_okvim/vim/state.py), [status.py](spyder_okvim/vim/status.py), [cursor.py](spyder_okvim/vim/cursor.py), [executor_visual.py](spyder_okvim/executor/executor_visual.py), [action_helpers.py](spyder_okvim/utils/action_helpers.py), [vim_widgets.py](spyder_okvim/spyder/vim_widgets.py).

수정량 순서와 실제 착수 순서는 다를 수 있다. 특히 07의 검색 무한 반복 방지는 해당 항목의 나머지 작업과 분리해 먼저 수정할 수 있다. 선행 권장 표시는 구현 시의 참고 사항이며, 전체 목록의 정렬 기준은 수정량이다.
