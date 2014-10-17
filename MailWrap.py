from AppKit import *
from Foundation import *
import objc
import textwrap

def fill(text, level):
    initial = subsequent = len(text) - len(text.lstrip())
    width = EditingMessageWebView._wrapWidth
    if EditingMessageWebView._bulletLists and initial > 0:
        if text.lstrip().startswith(('- ', '+ ', '* ')):
            subsequent += 2
    return textwrap.fill(' '.join(text.split()),
                         width - level - 1 if level > 0 else width,
                         break_long_words = False,
                         break_on_hyphens = False,
                         initial_indent = ' ' * initial,
                         subsequent_indent = ' ' * subsequent)

def swizzle(cls, sel):
    def decorator(fun):
        original = cls.instanceMethodForSelector_(sel)
        if original.isClassMethod:
            original = cls.methodForSelector_(sel)
        def wrapper(self, *args, **kwargs):
            return fun(self, original, *args, **kwargs)
        new = objc.selector(wrapper, selector = original.selector,
                            signature = original.signature,
                            isClassMethod = original.isClassMethod)
        objc.classAddMethod(cls, sel, new)
        return wrapper
    return decorator


class EditingMessageWebView(objc.Category(objc.runtime.EditingMessageWebView)):
    @swizzle(objc.runtime.EditingMessageWebView, 'decreaseIndentation:')
    def decreaseIndentation_(self, original, sender):
        # Call the original Mail.app decreaseIndentation: selector for rich
        # text messages.

        if self.contentElement().className() != 'ApplePlainTextBody':
            return original(self, sender)

        # If we have a selection, remove indentation on all lines which
        # overlap it. Otherwise, remove indentation on the line containing
        # the cursor. Combine the operation into a single undo group for UI
        # purposes.

        self.undoManager().beginUndoGrouping()
        affinity = self.selectionAffinity()
        selection = self.selectedDOMRange()
        if self.selectedRange().length == 0:
            self.moveToBeginningOfParagraph_(None)
            self.moveToEndOfParagraphAndModifySelection_(None)
            if not self.selectedText().strip():
                if self.selectedText():
                    self.deleteBackward_(None)
            elif self.selectedText()[:self._indentWidth].isspace():
                self.moveToBeginningOfParagraph_(None)
                for _ in xrange(self._indentWidth):
                    self.deleteForward_(None)
        else:
            last = self.selectedRange().length
            self.moveToEndOfDocumentAndModifySelection_(None)
            last = self.selectedRange().length - last
            while self.selectedRange().length > last:
                self.moveToBeginningOfParagraph_(None)
                self.moveToEndOfParagraphAndModifySelection_(None)
                if not self.selectedText().strip():
                    if self.selectedText():
                        self.deleteBackward_(None)
                elif self.selectedText()[:self._indentWidth].isspace():
                    self.moveToBeginningOfParagraph_(None)
                    for _ in xrange(self._indentWidth):
                        self.deleteForward_(None)
                self.moveToEndOfParagraph_(None)
                self.moveForward_(None)
                self.moveToEndOfDocumentAndModifySelection_(None)
            self.moveBackward_(None)
        self.setSelectedDOMRange_affinity_(selection, affinity)
        self.undoManager().endUndoGrouping()

    def fillParagraph(self):
        # Note the quote level of the current paragraph and the location of
        # the end of the message to avoid attempts to move beyond it.

        self.moveToEndOfDocumentAndModifySelection_(None)
        last = self.selectedRange().location + self.selectedRange().length

        self.moveToBeginningOfParagraph_(None)
        self.selectParagraph_(None)
        level = self.quoteLevelAtStartOfSelection()

        # If we are on a blank line, move down to the start of the next
        # paragraph block and finish.

        if not self.selectedText().strip():
            while True:
                self.moveDown_(None)
                self.selectParagraph_(None)
                location = self.selectedRange().location
                if location + self.selectedRange().length >= last:
                    self.moveToEndOfParagraph_(None)
                    return
                if self.selectedText().strip():
                    self.moveToBeginningOfParagraph_(None)
                    return

        # Otherwise move to the start of this paragraph block, working
        # upward until we hit the start of the message, a blank line or a
        # change in quote level.

        while self.selectedRange().location > 0:
            self.moveUp_(None)
            if self.quoteLevelAtStartOfSelection() != level:
                self.moveDown_(None)
                break
            self.selectParagraph_(None)
            if not self.selectedText().strip():
                self.moveDown_(None)
                break
        self.moveToBeginningOfParagraph_(None)

        # Insert a temporary placeholder space character to avoid any
        # assumptions about Mail.app's strange and somewhat unpredictable
        # handling of newlines between block elements.

        self.insertText_(' ')
        self.moveToEndOfParagraphAndModifySelection_(None)

        # Now extend the selection forward line-by-line until we hit a blank
        # line, a change in quote level or the end of the message.

        affinity = self.selectionAffinity()
        selection = self.selectedDOMRange()
        while True:
            location = self.selectedRange().location
            if location + self.selectedRange().length >= last:
                break
            self.moveDown_(None)
            self.moveToEndOfParagraphAndModifySelection_(None)
            if self.quoteLevelAtStartOfSelection() != level:
                break
            if not self.selectedText().strip():
                break
            selection.setEnd__(self.selectedDOMRange().endContainer(),
                               self.selectedDOMRange().endOffset())
        self.setSelectedDOMRange_affinity_(selection, affinity)

        # Finally, extend the selection forward to encompass any blank lines
        # following the paragraph block, regardless of quote level. Store
        # the minimum quote level of this paragraph block and the next.

        while True:
            location = self.selectedRange().location
            if location + self.selectedRange().length >= last:
                minimum = 0
                break
            self.moveDown_(None)
            self.moveToBeginningOfParagraph_(None)
            self.moveToEndOfParagraphAndModifySelection_(None)
            if self.selectedText().strip():
                minimum = min(self.quoteLevelAtStartOfSelection(), level)
                break
            selection.setEnd__(self.selectedDOMRange().endContainer(),
                               self.selectedDOMRange().endOffset())
        self.setSelectedDOMRange_affinity_(selection, affinity)

        # Re-fill the text allowing for quote level and retaining block
        # indentation, then insert it to replace the selection.

        text = fill(self.selectedText().expandtabs(), level) + '\n'
        self.insertTextWithoutReplacement_(text)

        # Reduce the quote level of the trailing blank line if necessary,
        # then remove the placeholder character and position the cursor at
        # the start of the next paragraph block.

        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            'Decrease', 'changeQuoteLevel:', '')
        item.setTag_(-1)
        for _ in xrange(level - minimum):
            self.changeQuoteLevel_(item)

        selection = self.selectedDOMRange()
        for _ in xrange(text.count('\n')):
            self.moveUp_(None)
            self.moveToBeginningOfParagraph_(None)
        self.deleteForward_(None)
        self.setSelectedDOMRange_affinity_(selection, affinity)
        self.moveForward_(None)

    def fillText(self):
        # MailWrap only works correctly on plain text messages, so ignore
        # any requests to format paragraphs in rich-text/HTML messages.

        if self.contentElement().className() != 'ApplePlainTextBody':
            return

        # If we have a selection, format all paragraph blocks which overlap
        # it. Otherwise, format the paragraph block containing the cursor.
        # Combine the operation into a single undo group for UI purposes.

        self.undoManager().beginUndoGrouping()
        if self.selectedRange().length == 0:
            self.fillParagraph()
            self.moveToEndOfDocumentAndModifySelection_(None)
        else:
            last = self.selectedRange().length
            self.moveToEndOfDocumentAndModifySelection_(None)
            last = self.selectedRange().length - last
            while self.selectedRange().length > last:
                self.fillParagraph()
                self.moveToEndOfDocumentAndModifySelection_(None)
        if self.selectedRange().length > 0:
            self.moveBackward_(None)
        else:
            self.deleteBackward_(None)
        self.undoManager().endUndoGrouping()

    @swizzle(objc.runtime.EditingMessageWebView, 'increaseIndentation:')
    def increaseIndentation_(self, original, sender):
        # Call the original Mail.app increaseIndentation: selector for rich
        # text messages.

        if self.contentElement().className() != 'ApplePlainTextBody':
            return original(self, sender)

        # If we have a selection, indent all lines which overlap it.
        # Otherwise, indent the line containing the cursor. Combine the
        # operation into a single undo group for UI purposes.

        self.undoManager().beginUndoGrouping()
        affinity = self.selectionAffinity()
        selection = self.selectedDOMRange()
        if self.selectedRange().length == 0:
            self.moveToBeginningOfParagraph_(None)
            self.insertText_(' ' * self._indentWidth)
            self.moveToBeginningOfParagraph_(None)
            self.moveToEndOfParagraphAndModifySelection_(None)
            if not self.selectedText().strip():
                self.deleteBackward_(None)
        else:
            last = self.selectedRange().length
            self.moveToEndOfDocumentAndModifySelection_(None)
            last = self.selectedRange().length - last
            while self.selectedRange().length > last:
                self.moveToBeginningOfParagraph_(None)
                self.insertText_(' ' * self._indentWidth)
                self.moveToBeginningOfParagraph_(None)
                self.moveToEndOfParagraphAndModifySelection_(None)
                if self.selectedText().strip():
                    self.moveForward_(None)
                else:
                    self.deleteBackward_(None)
                self.moveForward_(None)
                self.moveToEndOfDocumentAndModifySelection_(None)
        self.moveBackward_(None)
        self.setSelectedDOMRange_affinity_(selection, affinity)
        self.undoManager().endUndoGrouping()

    def insertTextWithoutReplacement_(self, text):
        if self.isAutomaticTextReplacementEnabled():
            self.setAutomaticTextReplacementEnabled_(False)
            self.insertText_(text)
            self.setAutomaticTextReplacementEnabled_(True)
        else:
            self.insertText_(text)

    def quoteLevelAtStartOfSelection(self):
        return self.selectedDOMRange().startContainer().quoteLevel()

    def selectedText(self):
        return self.selectedDOMRange().stringValue() or ''

    def wrapLine(self):
        # Select the current line, and break it into lines of the correct
        # width, allowing for quoting overhead and retaining the
        # indentation.

        self.moveToBeginningOfParagraph_(None)
        self.moveToEndOfParagraphAndModifySelection_(None)

        # Wrap the line allowing for quote level and retaining indentation,
        # then insert it to replace the selection.

        level = self.quoteLevelAtStartOfSelection()
        text = fill(self.selectedText().expandtabs(), level)

        # Insert the wrapped text to replace the selection, temporarily
        # disabling text replacement to avoid unintended substitutions.
        # Finally, position the cursor at the start of the next line.

        self.insertTextWithoutReplacement_(text)
        self.moveForward_(None)

    def wrapText(self):
        # MailWrap only works correctly on plain text messages, so ignore
        # any requests to format paragraphs in rich-text/HTML messages.

        if self.contentElement().className() != 'ApplePlainTextBody':
            return

        # If we have a selection, wrap all lines which overlap it.
        # Otherwise, wrap the line containing the cursor. Combine the
        # operation into a single undo group for UI purposes.

        self.undoManager().beginUndoGrouping()
        if self.selectedRange().length == 0:
            self.wrapLine()
        else:
            last = self.selectedRange().length
            self.moveToEndOfDocumentAndModifySelection_(None)
            last = self.selectedRange().length - last
            while self.selectedRange().length > last:
                self.wrapLine()
                self.moveToEndOfDocumentAndModifySelection_(None)
            if self.selectedRange().length > 0:
                self.moveBackward_(None)
        self.undoManager().endUndoGrouping()


class DocumentEditor(objc.Category(objc.runtime.DocumentEditor)):
    @swizzle(objc.runtime.DocumentEditor, 'finishLoadingEditor')
    def finishLoadingEditor(self, original):
        # Let Mail.app complete its own preparation of the new message and
        # the document editor before we do our own cleanups.

        original(self)

        if self.messageType() in [1, 2]:
            # We only modify messages resulting from a reply or reply-to-all
            # action. Begin by stripping stray blank lines at the beginning
            # of the message body and around cited text.

            view = self.webView()
            document = view.mainFrame().DOMDocument()

            view.contentElement().removeStrayLinefeeds()
            blockquotes = document.getElementsByTagName_('BLOCKQUOTE')
            for index in xrange(blockquotes.length()):
                if blockquotes.item_(index):
                    blockquotes.item_(index).removeStrayLinefeeds()

            # If we are configured to fix the attribution string, remove the
            # 'On DATE, at TIME, ' prefix from the first line, which will
            # always be the attribution in an unmodified reply. Also ensure
            # that the attribution and the blank line following it are not
            # incorrectly quoted by a bug in Mail.app 8.0.

            if self._fixAttribution:
                view.moveToBeginningOfDocument_(None)
                view.moveToEndOfParagraphAndModifySelection_(None)
                view.moveForwardAndModifySelection_(None)
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    'Decrease', 'changeQuoteLevel:', '')
                item.setTag_(-1)
                view.changeQuoteLevel_(item)

                attribution = view.selectedDOMRange().stringValue()
                attribution = attribution.rsplit(',', 1)[-1].lstrip()
                if view.isAutomaticTextReplacementEnabled():
                    view.setAutomaticTextReplacementEnabled_(False)
                    view.insertText_(attribution)
                    view.setAutomaticTextReplacementEnabled_(True)
                else:
                    view.insertText_(attribution)

            # Place the cursor at the end of the quoted text but before the
            # signature if present, separated from the quoted text by a
            # blank line.

            signature = document.getElementById_('AppleMailSignature')
            if signature:
                range = document.createRange()
                range.selectNode_(signature)
                view.setSelectedDOMRange_affinity_(range, 0)
                view.moveUp_(None)
            else:
                view.moveToEndOfDocument_(None)

            view.insertParagraphSeparator_(None)
            view.insertParagraphSeparator_(None)
            view.undoManager().removeAllActions()
            self.backEnd().setHasChanges_(False)


class MailWrap(objc.runtime.MVMailBundle):
    @classmethod
    def initialize(cls):
        # Register ourselves as a Mail.app plugin and add an entry for our
        # 'Fill Text' and Wrap Text' actions to the Edit menu.

        application = NSApplication.sharedApplication()
        bundle  = NSBundle.bundleWithIdentifier_('uk.me.cdw.MailWrap')
        cls.registerBundle()

        editmenu = application.mainMenu().itemAtIndex_(2).submenu()
        editmenu.addItem_(NSMenuItem.separatorItem())

        mask = NSCommandKeyMask
        editmenu.addItemWithTitle_action_keyEquivalent_('Fill Text',
            'fillText', '\\').setKeyEquivalentModifierMask_(mask)

        mask = NSCommandKeyMask | NSAlternateKeyMask
        editmenu.addItemWithTitle_action_keyEquivalent_('Wrap Text',
            'wrapText', '\\').setKeyEquivalentModifierMask_(mask)

        # Read our configuration settings if present. Otherwise, set the
        # correct default values.

        if bundle.objectForInfoDictionaryKey_('BulletLists') == False:
            EditingMessageWebView._bulletLists = False
        else:
            EditingMessageWebView._bulletLists = True

        if bundle.objectForInfoDictionaryKey_('FixAttribution') == False:
            DocumentEditor._fixAttribution = False
        else:
            DocumentEditor._fixAttribution = True

        indent = bundle.objectForInfoDictionaryKey_('IndentWidth')
        if isinstance(indent, (int, long)):
            EditingMessageWebView._indentWidth = width
        else:
            EditingMessageWebView._indentWidth = 2

        width = bundle.objectForInfoDictionaryKey_('WrapWidth')
        if isinstance(width, (int, long)):
            EditingMessageWebView._wrapWidth = width
        else:
            EditingMessageWebView._wrapWidth = 76

        # Report the plugin name and version to the com.apple.mail log.

        version = bundle.objectForInfoDictionaryKey_('CFBundleVersion')
        NSLog('Loaded MailWrap %s' % version)
