/**

 * Maylén — animación avatar en barra IA (/academy).

 */

(function () {

  'use strict';



  var actors = [];



  function MaylenActor(root) {

    this.root = root;

    this.photo = root.querySelector('.maylen-mentor-avatar__photo--live');

    this.wave = root.querySelector('.maylen-wave-emoji--academy');

    this.waveBoost = 0;

    this.start = performance.now();

  }



  MaylenActor.prototype.tick = function (now) {

    var t = (now - this.start) / 1000;

    var boost = Math.max(0, this.waveBoost);

    this.waveBoost = Math.max(0, this.waveBoost - 0.018);



    var breath = Math.sin(t * 1.55) * (4 + boost * 4);

    var rot = Math.sin(t * 1.15) * (3 + boost * 3);

    var scale = 1 + Math.sin(t * 1.55) * 0.03 + boost * 0.025;



    if (this.photo) {

      this.photo.style.transform =

        'translateY(' + breath.toFixed(2) + 'px) rotate(' + rot.toFixed(2) + 'deg) scale(' + scale.toFixed(3) + ')';

    }

    if (this.wave) {

      var wr = Math.sin(t * 5.5 + boost * 2) * (18 + boost * 14);

      var ws = 1 + Math.abs(Math.sin(t * 5.5)) * 0.15 + boost * 0.1;

      this.wave.style.transform = 'rotate(' + wr.toFixed(1) + 'deg) scale(' + ws.toFixed(2) + ')';

    }

  };



  MaylenActor.prototype.playWave = function () {

    this.waveBoost = 1;

  };



  function loop(now) {

    for (var i = 0; i < actors.length; i++) {

      actors[i].tick(now);

    }

    requestAnimationFrame(loop);

  }



  function init() {

    document.querySelectorAll('.maylen-avatar-live--academy[data-maylen-live="1"]').forEach(function (node) {

      actors.push(new MaylenActor(node));

    });

    if (actors.length) requestAnimationFrame(loop);



    window.playMaylenAcademyWave = function () {

      actors.forEach(function (a) {

        a.playWave();

      });

    };

  }



  if (document.readyState === 'loading') {

    document.addEventListener('DOMContentLoaded', init);

  } else {

    init();

  }

})();


