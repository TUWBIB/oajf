// highlights all occurrences of the keyword in the string
// the keyword is case-insensitive, thus highlighting all occurrences no matter the case
// treat '&' and 'and' interchangeably
function highlight(string, keyword) {

    console.log(string);
    console.log(keyword);

    keyword = keyword.replace('&amp;','&');
    const rex = new RegExp(keyword, "gi");
    const re1 = new RegExp(keyword.replace(' and', ' &'), "gi");
    const re2 = new RegExp(keyword.replace(' &', ' and'), "gi");
    let index = 0;
    let found = 0;
    const original = string;
    var string = "";
    
    var processMatches = function(regex) {
        let x = original.matchAll(regex);
        let y = Array.from(x);
        if (y.length > 0) {
            found = 1;
            for (i = 0; i < y.length; ++i) {
                str = y[i];
                string = string + original.substring(index, str.index) + 
                        $("<span>").css('background-color', 'yellow').text(str[0]).prop('outerHTML');
                index = str.index + str[0].length;
            }
            return true;
        }
        return false;
    };
    
    if (found == 0) {
        processMatches(rex);
    }
    if (found == 0) {
        processMatches(re1);
    }
    if (found == 0) {
        processMatches(re2);
    }
    
    return string + original.substring(index);
}
