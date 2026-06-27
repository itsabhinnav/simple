import {
  Directive,
  ElementRef,
  OnDestroy,
  OnInit,
  inject,
  effect,
  NgZone,
  PLATFORM_ID,
} from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { TranslationService } from './translation.service';

/**
 * AutoTranslateDirective
 *
 * Drop-in directive that walks the host element's subtree and rewrites
 * English text content / placeholder / title / aria-label attributes to
 * Japanese using `TranslationService.translateLiteral` whenever the
 * current language is `ja`.
 *
 * - Reactive: re-runs whenever `TranslationService.currentLang` flips.
 * - Idempotent: only writes when the translation differs from the existing
 *   text, so it does not loop with its own MutationObserver.
 * - Angular-friendly: setting `textContent` is observed by the directive;
 *   if Angular re-renders an interpolated text node (e.g. `{{ value }}`)
 *   the observer kicks in again and re-translates the new content.
 * - Skips inputs / textareas / contenteditable so the user's typed text
 *   is never clobbered.
 */
@Directive({
  selector: '[appAutoTranslate]',
  standalone: true,
})
export class AutoTranslateDirective implements OnInit, OnDestroy {
  private el = inject(ElementRef<HTMLElement>);
  private trans = inject(TranslationService);
  private zone = inject(NgZone);
  private isBrowser = isPlatformBrowser(inject(PLATFORM_ID));

  private observer?: MutationObserver;
  private rafHandle: number | null = null;

  constructor() {
    // Re-translate the entire subtree whenever the language flips.
    effect(() => {
      this.trans.currentLang();
      if (this.isBrowser) {
        this.scheduleWalk();
      }
    });
  }

  ngOnInit() {
    if (!this.isBrowser) return;

    this.zone.runOutsideAngular(() => {
      this.observer = new MutationObserver(() => this.scheduleWalk());
      this.observer.observe(this.el.nativeElement, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
        attributeFilter: ['placeholder', 'title', 'aria-label'],
      });
    });

    this.scheduleWalk();
  }

  ngOnDestroy() {
    this.observer?.disconnect();
    if (this.rafHandle !== null && this.isBrowser) {
      cancelAnimationFrame(this.rafHandle);
    }
  }

  private scheduleWalk() {
    if (!this.isBrowser) return;
    if (this.rafHandle !== null) return;
    this.rafHandle = requestAnimationFrame(() => {
      this.rafHandle = null;
      this.walk(this.el.nativeElement);
    });
  }

  private shouldSkip(el: HTMLElement): boolean {
    return el.hasAttribute('data-no-translate') || el.classList.contains('no-translate');
  }

  private walk(node: Node) {
    if (node.nodeType === Node.TEXT_NODE) {
      const original = node.textContent ?? '';
      if (!original.trim()) return;
      const leading = original.match(/^\s*/)?.[0] ?? '';
      const trailing = original.match(/\s*$/)?.[0] ?? '';
      const core = original.slice(leading.length, original.length - trailing.length);
      const translated = this.trans.translateLiteral(core);
      if (translated !== core) {
        node.textContent = leading + translated + trailing;
      }
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const el = node as HTMLElement;
    if (this.shouldSkip(el)) return;
    const tag = el.tagName?.toLowerCase();
    if (
      tag === 'script' ||
      tag === 'style' ||
      tag === 'input' ||
      tag === 'textarea' ||
      el.isContentEditable
    ) {
      // Still translate placeholder / title on form fields.
      this.translateAttrs(el);
      return;
    }

    this.translateAttrs(el);

    const children = el.childNodes;
    for (let i = 0; i < children.length; i++) {
      this.walk(children[i]);
    }
  }

  private translateAttrs(el: HTMLElement) {
    for (const attr of ['placeholder', 'title', 'aria-label']) {
      if (!el.hasAttribute(attr)) continue;
      const value = el.getAttribute(attr) ?? '';
      if (!value.trim()) continue;
      const translated = this.trans.translateLiteral(value);
      if (translated !== value) {
        el.setAttribute(attr, translated);
      }
    }
  }
}
