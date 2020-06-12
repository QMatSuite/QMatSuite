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
package main.java.com.consts;

public enum BravaisLattice {
	//ibrav
	v0(0,"free"), 
	v1(1,"simple cubic (sc)"),
	v2(2,"face centered cubic(fcc)"),
	v3(3,"body centered cubic(bcc)"),
    v4(4,"Hexagonal and Trigonal P"),
    v5(5,"Trigonal R"),
    v6(6,"Tetragonal P (st)"),
    v7(7,"Tetragonal I (bct)"),
    v8(8,"Orthorhombic P"),
    v9(9,"Orthorhombic base-centered(bco)"),
	v10(10,"Orthorhombic face-centered"),
	v11(11,"Orthorhombic body-centered"),
	v12(12,"Monoclinic P"),
	v13(13,"Monoclinic base-centered"),
	v14(14,"Triclinic");
	
	private int ind;
	private String name;
	
	private BravaisLattice(int ind, String name) {
		this.ind = ind;
        this.name = name;
    }
	@Override
	public String toString() {
		return name;
	}
	
	public static BravaisLattice fromInd(Integer ind){
		if (ind==null) return null;
        for(BravaisLattice e:BravaisLattice.values()){
            if(e.getInd()==ind){
                return e;
            }
        }
        return null;
    }

	public int getInd() {
		return ind;
	}

	public void setInd(int ind) {
		this.ind = ind;
	}

	public String getName() {
		return name;
	}

	public void setName(String name) {
		this.name = name;
	}

}
