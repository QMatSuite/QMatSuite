/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.centerWindow;

import javafx.scene.Group;
import javafx.scene.transform.Rotate;
import javafx.scene.transform.Translate;

public class GeoGroup extends Group{
	        
    public Translate t = new Translate();
    public Rotate rx = new Rotate();{ rx.setAxis(Rotate.X_AXIS); }
    public Rotate ry = new Rotate();{ ry.setAxis(Rotate.Y_AXIS); }
    public Rotate rz = new Rotate();{ rz.setAxis(Rotate.Z_AXIS); }
    
    public GeoGroup() {
		super();
        getTransforms().addAll(t, rz, ry, rx);
	}

    public void rotateAlongX(double x) { rx.setAngle(x); }
    public void rotateAlongY(double y) { ry.setAngle(y); }
    public void rotateAlongZ(double z) { rz.setAngle(z); }

}
