import { Injectable, signal } from '@angular/core';

export type Lang = 'en' | 'ja';

@Injectable({
  providedIn: 'root'
})
export class TranslationService {
  currentLang = signal<Lang>('en');

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
      'login.password_min': 'Password is required (min 6 characters)',
      'login.secret_key_min': 'Secret key is required (min 3 characters)',
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
      'nav.new_requirement': '要件作成',
      'nav.new_testcase': 'テストケース作成',
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
      'login.password_min': 'パスワードは必須項目です（6文字以上）',
      'login.secret_key_min': '秘密鍵は必須項目です（3文字以上）',
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

  translate(key: string): string {
    const lang = this.currentLang();
    return this.translations[lang]?.[key] || key;
  }
}
