function Spinner(canvas_sp, size){
  var rate = 40;
  var so2 = size/2;
  var lwidth = 1.5;
  var circ = 2 * Math.PI
  var curve = [
    {angle: 4 * circ/8, rad: so2, dir: 1, arc: circ/8}, 
    {angle: 8 * circ/8, rad: so2, dir: 1, arc: circ/8},
    {angle: 3 * circ/8, rad: so2 - 2, dir: -1, arc: circ/6}, 
    {angle: 7 * circ/8, rad: so2 - 2, dir: -1, arc: circ/6},
    {angle: 1.75 * circ/8, rad: so2 - 4, dir: 1, arc: circ/5}, 
    {angle: 5.75 * circ/8, rad: so2 - 4, dir: 1, arc: circ/5},
    {angle: 4.75 * circ/8, rad: so2 - 6, dir: -1, arc: circ/5, fill: true}, 
    {angle: 0.75 * circ/8, rad: so2 - 6, dir: -1, arc: circ/5, fill: true}
  ];
  var speed = 0.25;
  console.log(canvas_sp);
  canvas_sp.width = size;
  canvas_sp.height = size;
  var ctx_sp = canvas_sp.getContext('2d');
  this.stopper = setInterval(spin, rate);
  var step = 0;
  
  function spin(){
    ctx_sp.clearRect(0,0,size,size);
    var speed_mult = 1;// + Math.sin(step * 0.02)*0.4;
    step++;

    for(var i = 0; i < curve.length; i++){
      var c = curve[i];
      var fill = typeof(c.fill) != 'undefined';
      curve[i].angle += speed * c.dir * speed_mult;
      ctx_sp.beginPath();
      ctx_sp.lineWidth = lwidth;
      if (fill){
        ctx_sp.beginPath();
        ctx_sp.moveTo(so2, so2);
      }
      ctx_sp.arc(so2, so2, c.rad - lwidth, c.angle, c.angle + c.arc, false);
      ctx_sp.strokeStyle = "#444";
      ctx_sp.fillStyle = '#444';
      if (fill){
        ctx_sp.fill();
        ctx_sp.closePath();
      }
      ctx_sp.stroke();
    }
  }
  
  this.stop = function(){
    clearInterval(this.stopper);
    ctx_sp.clearRect(0,0,size,size);
  }
}

$(document).ready(function(){
  $.each($('.spinner'), function(){
    Spinner(this, 22);
  });
});
