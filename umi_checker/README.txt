I had a cool idea...

Plot the top N unique sequences on the X axis and the CV on the Y axis, so for a healthy UMI file there will
be a flat curve, but for a bad one there will be a spike. Let's give it a try.

1) Make a script that makes a histo of the sequences. How do I stop this getting out of hand memory-wise?

https://pypi.org/project/morris-counter/

Hmmm. But this still uses a lot of memory if you have lots of possible values. Is there a better one?

https://pypi.org/project/lossycount/


