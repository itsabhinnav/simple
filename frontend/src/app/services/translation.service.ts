import { Injectable, signal } from '@angular/core';

export type Lang = 'en' | 'ja';

@Injectable({
  providedIn: 'root'
})
export class TranslationService {
  currentLang = signal<Lang>('en');

  // Keyed translations (slug → string per language). Used for templates that
  // explicitly call the translate pipe with a slug like 'nav.create'.
  private translations: Record<Lang, Record<string, string>> = {
    en: {
      'Sakura': 'Sakura',
      'nav.search_placeholder': 'Search',
      'nav.create': 'Create',
      'nav.requirement': 'Requirement',
      'nav.requirement_desc': 'Create a new requirement',
      'nav.testcase': 'Test Case',
      'nav.testcase_desc': 'Create a new test case',
      'nav.design': 'Design',
      'nav.design_desc': 'Create a new design',
      'nav.specification': 'Specification',
      'nav.specification_desc': 'Manage and import specs',
      'nav.users': 'Users',
      'nav.logout': 'Logout',
      'nav.new_requirement': 'New Requirement',
      'nav.new_testcase': 'New Test Case',
      'nav.all_requirements': 'All Requirements',
      'nav.all_testcases': 'All Test Cases',
      'nav.search_result_req': '📋 Requirement',
      'nav.search_result_tc': '🧪 Test Case',
      'nav.search_result_design': '🎨 Design',

      'login.signin_title': 'Sign in to Sakura',
      'login.signup_title': 'Create your Sakura Account',
      'login.username': 'Username',
      'login.username_required': 'Username is required',
      'login.password': 'Password',
      'login.password_required': 'Password is required',
      'login.confirm_password': 'Confirm',
      'login.confirm_password_required': 'Please confirm your password',
      'login.passwords_dont_match': 'Passwords do not match',
      'login.email': 'Email',
      'login.email_required': 'Email is required',
      'login.email_invalid': 'Please enter a valid email',
      'login.first_name': 'First name',
      'login.last_name': 'Last name',
      'login.secret_key': 'Secret Key (for password recovery)',
      'login.secret_key_required': 'Secret key is required (min 3 characters)',
      'login.role': 'Role',
      'login.user_role': 'User',
      'login.admin_role': 'Admin',
      'login.create_account': 'Create account',
      'login.next': 'Next',
      'login.signin_instead': 'Sign in instead',
      'login.forgot_password': 'Forgot password?',
      'login.password_hint': 'Use 8 or more characters with a mix of letters, numbers & symbols',
      'login.secret_hint': 'Remember this key to recover your password if needed',
      'login.role_hint': 'Select your account role',
      'login.role_select_hint': 'Select your account role',
      'login.login_title': 'Login to your account',
      'login.login_button': 'Login',
      'login.logging_in': 'Logging in...',
      'login.signup_button': 'Sign Up',
      'login.creating_account': 'Creating account...',
      'login.no_account': "Don't have an account?",
      'login.has_account': 'Already have an account?',
      'login.username_min': 'Username is required (min 1 character)',
      'login.password_min': 'Password must be at least 12 characters',
      'login.secret_key_min': 'Secret key must be at least 12 characters',
      'login.first_name_opt': 'First Name (Optional)',
      'login.last_name_opt': 'Last Name (Optional)',
      'login.secret_placeholder': 'Enter a secret key to recover your password',

      'dashboard.requirements': 'Requirements',
      'dashboard.test_cases': 'Test Cases',
      'dashboard.designs': 'Designs',
      'dashboard.specifications': 'Specifications',
      'dashboard.user_management': 'User Management',
      'dashboard.import': 'Import',
      'dashboard.view_all': 'View all',
      'dashboard.loading': 'Loading...',
      'dashboard.manage_users': 'Manage Users',
      'dashboard.admin': 'Admin',
      'dashboard.signin': 'Sign in',
      'dashboard.continue_to': 'to continue to',
    },
    ja: {
      'Sakura': 'さくら',
      'nav.search_placeholder': '検索',
      'nav.create': '新規作成',
      'nav.requirement': '要件',
      'nav.requirement_desc': '新しい要件を作成します',
      'nav.testcase': 'テストケース',
      'nav.testcase_desc': '新しいテストケースを作成します',
      'nav.design': 'デザイン',
      'nav.design_desc': '新しいデザインを作成します',
      'nav.specification': '仕様書',
      'nav.specification_desc': '仕様書の管理とインポートを行います',
      'nav.users': 'ユーザー管理',
      'nav.logout': 'ログアウト',
      'nav.new_requirement': '要件を作成',
      'nav.new_testcase': 'テストケースを作成',
      'nav.all_requirements': 'すべての要件',
      'nav.all_testcases': 'すべてのテストケース',
      'nav.search_result_req': '📋 要件',
      'nav.search_result_tc': '🧪 テストケース',
      'nav.search_result_design': '🎨 デザイン',

      'login.signin_title': 'Sakura にサインイン',
      'login.signup_title': 'Sakura アカウントの作成',
      'login.username': 'ユーザー名',
      'login.username_required': 'ユーザー名は必須項目です',
      'login.password': 'パスワード',
      'login.password_required': 'パスワードは必須項目です',
      'login.confirm_password': 'パスワード（確認）',
      'login.confirm_password_required': '確認用パスワードを入力してください',
      'login.passwords_dont_match': 'パスワードが一致しません',
      'login.email': 'メールアドレス',
      'login.email_required': 'メールアドレスは必須項目です',
      'login.email_invalid': '有効なメールアドレスを入力してください',
      'login.first_name': '名',
      'login.last_name': '姓',
      'login.secret_key': '秘密鍵（パスワード回復用）',
      'login.secret_key_required': '秘密鍵は必須項目です（3文字以上）',
      'login.role': '役割',
      'login.user_role': '一般ユーザー',
      'login.admin_role': '管理者',
      'login.create_account': 'アカウント作成',
      'login.next': '次へ',
      'login.signin_instead': '代わりにサインインする',
      'login.forgot_password': 'パスワードをお忘れですか？',
      'login.password_hint': '記号、英大文字・小文字、数字を含む8文字以上で指定してください',
      'login.secret_hint': 'パスワードの再設定に必要なため、この鍵を控えておいてください',
      'login.role_hint': 'アカウントの役割を選択してください',
      'login.role_select_hint': 'アカウントの役割を選択してください',
      'login.login_title': 'アカウントにログイン',
      'login.login_button': 'ログイン',
      'login.logging_in': 'ログイン中...',
      'login.signup_button': 'サインアップ',
      'login.creating_account': 'アカウント作成中...',
      'login.no_account': 'アカウントをお持ちでないですか？',
      'login.has_account': 'すでにアカウントをお持ちですか？',
      'login.username_min': 'ユーザー名は必須項目です（1文字以上）',
      'login.password_min': 'パスワードは12文字以上で入力してください',
      'login.secret_key_min': '秘密鍵は12文字以上で入力してください',
      'login.first_name_opt': '名（任意）',
      'login.last_name_opt': '姓（任意）',
      'login.secret_placeholder': 'パスワード回復用の秘密鍵を入力してください',

      'dashboard.requirements': '要件定義',
      'dashboard.test_cases': 'テストケース',
      'dashboard.designs': 'デザイン',
      'dashboard.specifications': '仕様書',
      'dashboard.user_management': 'ユーザー管理',
      'dashboard.import': 'インポート',
      'dashboard.view_all': 'すべて表示',
      'dashboard.loading': '読み込み中...',
      'dashboard.manage_users': 'ユーザー管理',
      'dashboard.admin': '管理者',
      'dashboard.signin': 'サインイン',
      'dashboard.continue_to': 'に進む',
    }
  };

  // Literal English → Japanese map. Used as a fallback so any component
  // (whether it routes through the translate pipe or not) can render
  // Japanese without the developer wiring per-key slugs everywhere.
  // Keys are exact-cased English snippets that appear in the UI; the
  // AutoTranslate directive walks the DOM and swaps text nodes that match
  // any entry here (case-insensitive lookup).
  private literalEnToJa: Record<string, string> = {
    // Common app chrome
    'Dashboard': 'ダッシュボード',
    'Requirements': '要件',
    'Requirements Management': '要件管理',
    'Requirement Management': '要件管理',
    'Requirement': '要件',
    'Test Cases': 'テストケース',
    'Test Case Management': 'テストケース管理',
    'Test Case': 'テストケース',
    'Test Case ID': 'テストケースID',
    'Designs': 'デザイン',
    'Design Tickets': 'デザインチケット',
    'Design Ticket Management': 'デザインチケット管理',
    'Specifications': '仕様書',
    'Spec Management': '仕様書管理',
    'Users': 'ユーザー',
    'User Management': 'ユーザー管理',
    'Logout': 'ログアウト',
    'Sign in': 'サインイン',
    'Sign Up': 'サインアップ',
    'Sign in instead': '代わりにサインインする',
    'Profile': 'プロフィール',
    'Settings': '設定',
    'Help': 'ヘルプ',
    'Home': 'ホーム',

    // Buttons & generic actions
    'Create': '作成',
    'Create Requirement': '要件を作成',
    'Create Test Case': 'テストケースを作成',
    'Create Design Ticket': 'デザインチケットを作成',
    'Add New': '新規追加',
    'Add New Test Case': '新しいテストケースを追加',
    'Add Requirement': '要件を追加',
    'Edit': '編集',
    'Update': '更新',
    'Save': '保存',
    'Save Changes': '変更を保存',
    'Cancel': 'キャンセル',
    'Delete': '削除',
    'Remove': '削除',
    'Confirm': '確認',
    'Confirm Delete': '削除の確認',
    'Submit': '送信',
    'Reset': 'リセット',
    'Apply': '適用',
    'Close': '閉じる',
    'Done': '完了',
    'Back': '戻る',
    'Next': '次へ',
    'Previous': '前へ',
    'Search': '検索',
    'Filter': 'フィルタ',
    'Filters': 'フィルタ',
    'More Filters': 'その他のフィルタ',
    'Clear': 'クリア',
    'Clear filters': 'フィルタをクリア',
    'Clear all filters': 'すべてのフィルタをクリア',
    'Clear selection': '選択をクリア',
    'Clear search': '検索をクリア',
    'Reload': '再読み込み',
    'Retry': '再試行',
    'Refresh': '更新',
    'View': '表示',
    'View Details': '詳細を表示',
    'View Full Details': '詳細を全て表示',
    'View all': 'すべて表示',
    'Import': 'インポート',
    'Export': 'エクスポート',
    'Import Test Cases': 'テストケースをインポート',
    'Import Test Cases from Excel': 'Excelからテストケースをインポート',
    'Import more': 'さらにインポート',
    'Upload': 'アップロード',
    'Download': 'ダウンロード',
    'Login': 'ログイン',
    'OK': 'OK',
    'Loading...': '読み込み中...',
    'Loading requirements...': '要件を読み込み中...',
    'Loading test cases...': 'テストケースを読み込み中...',
    'Loading designs...': 'デザインを読み込み中...',
    'Saving...': '保存中...',
    'Submitting...': '送信中...',
    'Creating...': '作成中...',
    'Updating...': '更新中...',
    'Deleting...': '削除中...',
    'Importing\u2026': 'インポート中\u2026',
    'Importing...': 'インポート中...',
    'Reading workbook\u2026': 'ワークブックを読み込み中\u2026',

    // Labels & form fields
    'ID': 'ID',
    'Title': 'タイトル',
    'Description': '説明',
    'Status': 'ステータス',
    'Priority': '優先度',
    'Severity': '重要度',
    'Type': '種別',
    'Test Type': 'テスト種別',
    'Requirement Type': '要件種別',
    'TestSuite Type': 'テストスイート種別',
    'Feature': '機能',
    'Screen ID': '画面ID',
    'Region': '地域',
    'Brand': 'ブランド',
    'Vehicle Model': '車両モデル',
    'Vehicle Variant': '車両バリアント',
    'Vehicle Specification': '車両仕様',
    'Assignee': '担当者',
    'Reporter': '報告者',
    'Created By': '作成者',
    'Created Date': '作成日',
    'Created From': '作成日（開始）',
    'Created To': '作成日（終了）',
    'Last Updated': '最終更新',
    'Tags': 'タグ',
    'Tag': 'タグ',
    'Category': 'カテゴリ',
    'Comment': 'コメント',
    'Comments': 'コメント',
    'Notes': 'メモ',
    'Date': '日付',
    'From': '開始',
    'To': '終了',
    'Sort By': '並び替え',
    'Order': '順序',
    'Ascending': '昇順',
    'Descending': '降順',

    // Filter helpers
    'Active': '有効',
    'Active:': 'アクティブ:',
    'Search by ID, title, description, assignee, tags, GWT...': 'ID・タイトル・説明・担当者・タグ・GWTで検索...',
    'Search requirements...': '要件を検索...',
    'Search test cases...': 'テストケースを検索...',
    'Search designs...': 'デザインを検索...',
    'Search...': '検索...',
    'All Statuses': 'すべてのステータス',
    'All Priorities': 'すべての優先度',
    'All Assignees': 'すべての担当者',
    'All Types': 'すべての種別',
    'All Severities': 'すべての重要度',
    'Any': '指定なし',
    'With Description': '説明あり',
    'Without Description': '説明なし',
    'Has description': '説明あり',
    'No description': '説明なし',
    '— Unassigned —': '— 未割り当て —',
    'Unassigned': '未割り当て',

    // Priority/severity labels
    'P1 - Critical': 'P1 - 最重要',
    'P2 - High': 'P2 - 高',
    'P3 - Medium': 'P3 - 中',
    'P4 - Low': 'P4 - 低',
    'Critical': '最重要',
    'High': '高',
    'Medium': '中',
    'Low': '低',
    'Blocker': 'ブロッカー',
    'Major': '高',
    'Minor': '低',
    'Trivial': '軽微',

    // Status labels
    'Draft': 'ドラフト',
    'Approved': '承認済み',
    'Implemented': '実装済み',
    'Tested': 'テスト済み',
    'Closed': 'クローズ',
    'Open': 'オープン',
    'In Progress': '進行中',
    'In Review': 'レビュー中',
    'Completed': '完了',
    'Archived': 'アーカイブ',
    'Pending': '保留中',
    'Rejected': '却下',
    'On Hold': '保留',

    // Test Case specifics
    'Procedure': '手順',
    'Preconditions': '前提条件',
    'Expected Behavior': '期待される動作',
    'Test Objective': 'テスト目的',
    'Associated Requirement': '関連要件',
    'Associated Requirement ID': '関連要件ID',
    'Reference Document': '参考資料',
    'Regulation': '規制',
    'Environment Dependency': '環境依存',
    'DR ID': 'DR ID',
    'DR Applicable Screens': 'DR適用画面',
    'Positive': '正常系',
    'Negative': '異常系',
    'Boundary': '境界値',
    'Performance': '性能',
    'Sanity': 'サニティ',
    'Smoke': 'スモーク',
    'Regression': 'リグレッション',
    'Functional': '機能',
    'Non-Functional': '非機能',
    'HMI': 'HMI',
    'Safety': '安全性',
    'Usability': '使いやすさ',

    // Requirement (BDD/GWT)
    'Given': '前提',
    'When': '操作',
    'Then': '結果',
    'Linked Spec': '関連仕様',

    // Empty / error states
    'No Requirements Found': '要件が見つかりません',
    'No Test Cases Found': 'テストケースが見つかりません',
    'No Designs Found': 'デザインが見つかりません',
    'No requirements available. Create your first requirement!': '要件がまだありません。最初の要件を作成しましょう！',
    'No test cases available. Create your first test case!': 'テストケースがまだありません。最初のテストケースを作成しましょう！',
    'No requirements match your filter criteria.': 'フィルタ条件に一致する要件はありません。',
    'No test cases match your filter criteria.': 'フィルタ条件に一致するテストケースはありません。',
    'Select an item from the list to view its details': 'リストから項目を選択して詳細を表示してください',
    'Select an item': '項目を選択',
    'Failed to load requirements': '要件の読み込みに失敗しました',
    'Failed to load test cases': 'テストケースの読み込みに失敗しました',
    'Failed to load designs': 'デザインの読み込みに失敗しました',
    'Failed to create requirement': '要件の作成に失敗しました',
    'Failed to update requirement': '要件の更新に失敗しました',
    'Failed to delete requirement': '要件の削除に失敗しました',
    'Failed to create test case': 'テストケースの作成に失敗しました',
    'Failed to update test case': 'テストケースの更新に失敗しました',
    'Failed to delete test case': 'テストケースの削除に失敗しました',
    'No item selected': '項目が選択されていません',
    'Are you sure you want to delete this requirement?': 'この要件を削除してもよろしいですか？',
    'Are you sure you want to delete test case': 'このテストケースを削除してもよろしいですか',
    'Are you sure you want to delete this test case?': 'このテストケースを削除してもよろしいですか？',
    'This action cannot be undone.': 'この操作は取り消せません。',

    // Modal & form
    'Edit Requirement': '要件を編集',
    'New Requirement': '新規要件',
    'New Test Case': '新規テストケース',
    'Edit Test Case': 'テストケースを編集',
    'Delete Test Case': 'テストケースを削除',
    'Delete Requirement': '要件を削除',

    // Pagination
    'Per page': '表示件数',
    'Page': 'ページ',
    'of': '/',
    'Prev': '前へ',
    '\u2039 Prev': '\u2039 前へ',
    'Next \u203A': '次へ \u203A',
    'Showing': '表示中',
    'rows': '行',
    'columns': '列',

    // Views
    'Grid View': 'グリッド表示',
    'Table View': 'テーブル表示',
    'Browse View': 'ブラウズ表示',
    'Browse / Split View (current)': 'ブラウズ／分割表示（現在）',
    'Split View': '分割表示',
    'List View': 'リスト表示',

    // Header / breadcrumbs
    'Actions': '操作',
    'Action': '操作',
    'Result': '結果',
    'Summary': 'サマリー',
    'Details': '詳細',
    'Detail': '詳細',
    'Information': '情報',
    'Overview': '概要',
    'History': '履歴',
    'Activity': 'アクティビティ',

    // Import flow
    'Review column mapping': '列マッピングの確認',
    'Confirm or fix the mapping for each column, then click Import.': '各列のマッピングを確認・修正のうえ、インポートをクリックしてください。',
    'Column in spreadsheet': 'スプレッドシートの列',
    'Maps to test-case field': 'マッピング先フィールド',
    'Sample value': 'サンプル値',
    '— Ignore this column —': '— この列を無視 —',
    'Import with this mapping': 'このマッピングでインポート',
    'Import (auto-detect)': 'インポート（自動検出）',
    'Preview & Map Columns': 'プレビューと列マッピング',
    'Replace existing rows with the same ID': '同じIDの既存行を置き換える',
    'Created:': '作成:',
    'Updated:': '更新:',
    'Skipped:': 'スキップ:',
    'Failed:': '失敗:',
    'Created': '作成',
    'Skipped': 'スキップ',
    'Failed': '失敗',
    'Updated': '更新',

    // Misc small phrases
    'Optional': '任意',
    'Required': '必須',
    'None': 'なし',
    'All': 'すべて',
    'No data': 'データなし',
    'No results': '該当する結果がありません',
    'Select...': '選択...',
    'Choose...': '選択してください...',
    'Search Type': '種別を検索',
    'Search Priority': '優先度を検索',
    'Search Severity': '重要度を検索',
    'Search Feature': '機能を検索',
    'Search Screen ID': '画面IDを検索',
    'Search TestSuite Type': 'テストスイート種別を検索',
    'Search Requirement Type': '要件種別を検索',
    'Search Vehicle Model': '車両モデルを検索',
    'Search Region': '地域を検索',
    'Search Brand': 'ブランドを検索',

    // Filter chip prefixes (also handled via tokenized translate below)
    'Search:': '検索:',
    'Status:': 'ステータス:',
    'Priority:': '優先度:',
    'Severity:': '重要度:',
    'Type:': '種別:',
    'Feature:': '機能:',
    'Screen:': '画面:',
    'TestSuite:': 'テストスイート:',
    'Req. Type:': '要件種別:',
    'Vehicle:': '車両:',
    'Region:': '地域:',
    'Brand:': 'ブランド:',
    'Tag:': 'タグ:',
    'Assignee:': '担当者:',
    'From:': '開始:',
    'To:': '終了:',
  };

  constructor() {
    if (typeof window !== 'undefined') {
      const savedLang = localStorage.getItem('lang') as Lang;
      if (savedLang === 'en' || savedLang === 'ja') {
        this.currentLang.set(savedLang);
      }
    }
  }

  setLanguage(lang: Lang) {
    this.currentLang.set(lang);
    if (typeof window !== 'undefined') {
      localStorage.setItem('lang', lang);
    }
  }

  /** Translate by slug (legacy keys) or fall back to literal text. */
  translate(key: string): string {
    const lang = this.currentLang();
    const fromSlug = this.translations[lang]?.[key];
    if (fromSlug) return fromSlug;
    if (lang === 'ja') {
      const lit = this.literalEnToJa[key];
      if (lit) return lit;
    }
    return key;
  }

  /** Translate a literal piece of English UI text to Japanese (or return
   * the input unchanged for English / unknown strings). Used by the
   * AutoTranslate directive that walks the DOM. */
  translateLiteral(text: string): string {
    if (this.currentLang() !== 'ja') return text;
    if (!text) return text;
    const direct = this.literalEnToJa[text];
    if (direct) return direct;
    // Try case-normalised lookup
    const trimmed = text.trim();
    if (trimmed !== text) {
      const t = this.literalEnToJa[trimmed];
      if (t) return text.replace(trimmed, t);
    }
    // Tokenised fallback for compound strings like "Status: Approved" or
    // "All Test Cases (12)". We replace English tokens that exist in our
    // dictionary while leaving punctuation / numbers / katakana intact.
    if (/[A-Za-z]/.test(text)) {
      const replaced = text.replace(/[A-Za-z][A-Za-z\s\-_/]+[A-Za-z]/g, (frag) => {
        const norm = frag.trim();
        return this.literalEnToJa[norm] || frag;
      });
      if (replaced !== text) return replaced;
    }
    return text;
  }
}
