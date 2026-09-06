import {addClass, readUserVisibleText} from '@/common/utils/common'

export class HtmlIFrameOutput {
    constructor() {
        this.element = document.createElement('iframe')
        addClass(this.element, 'html-iframe-output')

        this.element.style.border = 'none'
        this.element.style.fontFamily = 'monospace'
        this.element.style.padding = 0
    }

    clear() {
        this.element.srcdoc = ''
    }

    write(text) {
        this.element.srcdoc += text
    }

    removeInlineImage(outputPath) {

    }

    setInlineImage(outputPath, downloadUrl) {
        console.log('WARNING! inline images are not supported for html output')
    }

    // The iframe's content lives in a separate document (srcdoc), so innerText/textContent
    // on the <iframe> element itself are always empty - read from contentDocument instead.
    getText() {
        const body = this.element.contentDocument && this.element.contentDocument.body
        if (!body) {
            return ''
        }
        return readUserVisibleText(body)
    }

    // Returns the full rendered HTML document, so Download can offer a real, reopenable .html
    // file for html_iframe output instead of an empty/plain-text one.
    getHtml() {
        const doc = this.element.contentDocument
        if (!doc || !doc.documentElement) {
            return ''
        }
        return doc.documentElement.outerHTML
    }
}