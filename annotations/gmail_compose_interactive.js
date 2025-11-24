function waitForElm(selector) {
    return new Promise(resolve => {
        if (document.querySelector(selector)) {
            return resolve(document.querySelector(selector));
        }

        const observer = new MutationObserver(() => {
            const element = document.querySelector(selector);
            if (element) {
                observer.disconnect();
                resolve(element);
            }
        });

        observer.observe(document.body, { childList: true, subtree: true });
    });
}

window.addEventListener("load", function () {
    const targets = [
        "div.T-I.T-I-KE[role='button']",
        "input[aria-label='To recipients']",
        "input[name='subjectbox']",
        "div[aria-label='Message Body']",
        "//div[@role='button' and contains(@aria-label, 'Send')]"
    ];

    targets.forEach((selector) => {
        if (selector.startsWith("//")) {
            waitForElm("body").then(() => {
                const xpathResult = document.evaluate(
                    selector,
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                );
                if (xpathResult.singleNodeValue) {
                    xpathResult.singleNodeValue.setAttribute("data-taint", "1");
                }
            });
        } else {
            waitForElm(selector).then((elm) => {
                elm.setAttribute("data-taint", "1");
            });
        }
    });
});

